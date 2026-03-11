import os
import uuid

from dotenv import load_dotenv

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from haystack.dataclasses import ChatMessage
from haystack.tools import ComponentTool
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.models import (
    DocumentSourceType,
    ResponseModel,
    GraphResponse,
    BaseMetadata,
    JiraMetadata,
    ConfluenceMetadata,
    GitHubMetadata,
)
from src.core.knowledge_index import KnowledgeIndex
from src.core.document_chunk_writer import DocumentChunkWriter
from src.core.chunk_retriever import ChunkRetriever
from src.core.question_answering import QuestionAnswering
from src.core.knowledge_graph_service import KnowledgeGraphService
from src.core.relationship_manager import RelationshipManager

from src.core.atlassian.jira_loader import JiraLoader
from src.core.atlassian.confluence_loader import ConfluenceLoader
from src.core.git.github_loader import GitHubLoader
from src.core.chat_memory import ChatMemory

from src.core.settings import (
    create_llm_generator,
    create_text_embedder,
    create_document_embedder,
)

load_dotenv()

pipelines = {}
loaders = {}
chat_memory = ChatMemory(max_messages_per_session=50)

agent_chat_memory = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init loaders
    loaders["jira"] = JiraLoader(
        url=os.getenv("JIRA_URL"),
        username=os.getenv("JIRA_USERNAME"),
        api_key=os.getenv("JIRA_API_KEY"),
        projects=os.getenv("JIRA_PROJECTS", "").split(","),
    )
    loaders["confluence"] = ConfluenceLoader(
        url=os.getenv("CONFLUENCE_URL"),
        username=os.getenv("CONFLUENCE_USERNAME"),
        api_key=os.getenv("CONFLUENCE_API_KEY"),
        spaces=os.getenv("CONFLUENCE_SPACES", "").split(","),
    )
    loaders["github"] = GitHubLoader(
        repositories=os.getenv("GITHUB_REPOSITORIES", "").split(","),
        ref=os.getenv("GITHUB_REF", "main"),
        token=os.getenv("GITHUB_TOKEN"),
    )
    # Init RAG pipeline
    chunk_writer = DocumentChunkWriter(
        neo4j_url=os.getenv("NEO4J_URL"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        embedding_dim=int(os.getenv("EMBEDDING_DIMENSION", "768")),
    )
    # Create chunk retriever for querying embedded chunks
    chunk_retriever = ChunkRetriever(
        neo4j_url=os.getenv("NEO4J_URL"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        index_name=os.getenv("NEO4J_INDEX", "chunk_embeddings"),
        top_k=int(os.getenv("NEO4J_TOP_K", "5")),
    )
    # Create provider components centrally
    llm_generator = create_llm_generator()
    text_embedder = create_text_embedder()
    document_embedder = create_document_embedder()

    # pipelines["rag"] = QuestionAnswering(
    #     embedding_retriever=chunk_retriever,
    #     llm_generator=llm_generator,
    #     text_embedder=text_embedder,
    # )

    # Initialize relationship manager for tracking document links
    relationship_manager = RelationshipManager(
        neo4j_url=os.getenv("NEO4J_URL"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )

    pipelines["index"] = KnowledgeIndex(
        chunk_writer=chunk_writer,
        document_embedder=document_embedder,
        relationship_manager=relationship_manager,
    )
    pipelines["graph"] = KnowledgeGraphService(
        neo4j_url=os.getenv("NEO4J_URL"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )

    ###### TO BE MOVED ######
    from haystack.components.agents import Agent
    from haystack.components.generators.utils import print_streaming_chunk
    from haystack.components.generators.chat import OpenAIChatGenerator

    from haystack.components.agents.state import replace_values

    from src.tools.rag_search_tool import RAGSearch
    from src.tools.graph_query_tool import GraphQuery
    from src.tools.filter_docs_tool import FilterDocs
    from src.tools.fetch_neighbors_tool import FetchNeighbors

    def _docs_to_summary(documents: list) -> str:
        """Convert a list of Haystack Documents to a concise summary for the LLM."""
        if not documents:
            return "No documents found."
        lines = [f"Found {len(documents)} document(s):"]
        for i, doc in enumerate(documents, 1):
            meta = doc.meta if hasattr(doc, "meta") else {}
            doc_type = meta.get("type", "UNKNOWN")
            title = meta.get("title", meta.get("issue_key", meta.get("file_path", "Untitled")))
            source = meta.get("source", "")
            snippet = (doc.content or "")[:200].replace("\n", " ")
            lines.append(f"  [{i}] ({doc_type}) {title} — {snippet}...")
            if source:
                lines.append(f"      Source: {source}")
        lines.append("\nYou can now call fetch_neighbors_tool to expand context, filter_docs_tool to narrow results, or answer the question based on these documents.")
        return "\n".join(lines)

    rag_tool = ComponentTool(
        component=RAGSearch(
            embedding_retriever=chunk_retriever,
            text_embedder=text_embedder,
        ),
        name="rag_search_tool",
        description="Semantic search across all indexed documents (Jira, Confluence, GitHub). Use this for broad or conceptual questions where the user describes a topic, problem, or concept in natural language (e.g. 'How does our authentication flow work?', 'What is the deployment process?').",
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    graph_query_tool = ComponentTool(
        component=GraphQuery(
            neo4j_url=os.getenv("NEO4J_URL"),
            neo4j_username=os.getenv("NEO4J_USERNAME"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            chat_generator=create_llm_generator(),
        ),
        name="graph_query_tool",
        description="Direct property lookup in the knowledge graph. Use this when the user mentions a specific identifier such as a Jira ticket key (e.g. 'DEV-42'), a Confluence space key, a project key, a GitHub repo name, or a file path. Fast and precise — best for targeted lookups by known names or keys.",
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    filter_docs_tool = ComponentTool(
        component=FilterDocs(),
        name="filter_docs_tool",
        description="Filter the documents already retrieved in the current conversation. Use this AFTER rag_search_tool or graph_query_tool when the initial search returned too many results and you need to narrow them down to only the most relevant ones for the user's question.",
        inputs_from_state={"documents": "documents"},
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    fetch_neighbors_tool = ComponentTool(
        component=FetchNeighbors(
            neo4j_url=os.getenv("NEO4J_URL"),
            neo4j_username=os.getenv("NEO4J_USERNAME"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        ),
        name="fetch_neighbors_tool",
        description="Expand context by fetching documents linked to the ones already retrieved via REFERENCES relationships in the graph. Use this AFTER an initial search when the user asks about related items, dependencies, or you need more surrounding context (e.g. 'What tickets are related to DEV-42?', 'Show me linked Confluence pages').",
        inputs_from_state={"documents": "documents"},
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    kraken_agent = Agent(
        chat_generator=OpenAIChatGenerator(model="gpt-4o-mini"),
        system_prompt="""
        You are Project Kraken, an AI assistant built on top of a central knowledge base containing information about an enterprise's documentation, processes, and data.

        ## Tool Selection Guide
        You have 4 tools. Choose the right one based on the user's query:

        1. **graph_query_tool** — Use FIRST when the user mentions a specific identifier: a Jira ticket key (e.g. DEV-42, PROJ-123), a Confluence space or page, a project key, a GitHub repository name, or a file path. This is the fastest and most precise lookup.

        2. **rag_search_tool** — Use when the user asks a broad or conceptual question in natural language (e.g. "How does authentication work?", "What is our deployment process?"). This performs a semantic search across all indexed content.

        3. **filter_docs_tool** — Use AFTER an initial search (graph_query_tool or rag_search_tool) returned too many documents. This narrows results down to the most relevant ones for the question.

        4. **fetch_neighbors_tool** — Use AFTER an initial search to **extend and enrich the context** by discovering documents linked to the ones already retrieved via graph relationships. This is critical when the initial results alone are not sufficient to fully answer the question. Actively use this tool to pull in related Jira tickets, linked Confluence pages, or referenced GitHub files so you can provide a more complete and well-informed answer. When in doubt about whether you have enough context, call this tool.

        ## Rules
        - Always use at least one search tool (graph_query_tool or rag_search_tool) before answering.
        - Only answer based on information found via the tools. Never fabricate or hallucinate information.
        - If no relevant information is found, ask the user for clarification or more details.
        - You may chain tools: search first, then filter or fetch neighbors to refine results.
        """,
        tools=[
            rag_tool,  # Search through the vector DB --> Extend with filters for documents types
            graph_query_tool, # Search through the knowledge graph/vector DB for documuments using cypher queries --> fast lookup with information retrieved from the users' text input
            filter_docs_tool, # Using the documents currently in scope, filter out irrelevant documents based on the user's question to narrow down the context and information available for answering the question
            fetch_neighbors_tool # Using the documents currently in scope, fetch related documents from the graph to expand the context and information available for answering the question
        ],
        state_schema={"documents": {"type": list, "handler": replace_values}},
        streaming_callback=print_streaming_chunk,
        max_agent_steps=5,
    )
    pipelines["agent"] = kraken_agent
    ###### TO BE MOVED ######

    yield
    # Clean up before shutdown
    pipelines.clear()


app = FastAPI(lifespan=lifespan)
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if session ID exists in cookies
        session_id = request.cookies.get("X-Session-ID")

        # Generate new session ID if not present
        if not session_id:
            session_id = str(uuid.uuid4())

        # Store session ID in request state for potential use in endpoints
        request.state.session_id = session_id

        # Call the next middleware/endpoint
        response = await call_next(request)

        # Set the session ID cookie on the response
        response.set_cookie(
            key="X-Session-ID",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            max_age=86400 * 30,  # 30 days
        )

        # Also set it as a response header for visibility
        response.headers["X-Session-ID"] = session_id

        return response


app.add_middleware(SessionMiddleware)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/index/stats")
async def get_index_stats():
    return {"count": pipelines["index"].get_index_stats()}


@app.post("/index/create")
async def create_index():
    docs = []
    for loader in loaders.values():
        if loader is None:
            continue
        loader_docs = await loader.load()
        docs.extend(loader_docs)
    if not docs:
        return {"status": "no documents to index"}
    pipelines["index"].create_index(docs)
    return {"status": "index created"}


@app.post("/index/clear")
async def clear_index():
    pipelines["index"].clear_index()
    chat_memory.clear_all()
    agent_chat_memory.clear()
    return {"status": "index cleared"}


from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    sources: list[str] = []


def _map_metadata(meta: dict) -> BaseMetadata:
    doc_type = meta.get("type")
    if doc_type == "JIRA":
        return JiraMetadata(**meta)
    elif doc_type == "CONFLUENCE":
        return ConfluenceMetadata(**meta)
    elif doc_type == "GITHUB":
        return GitHubMetadata(**meta)
    else:
        raise ValueError(f"Unknown document type: {doc_type}")


@app.post("/ask", response_model=ResponseModel)
async def answer_question(body: AskRequest, request: Request) -> ResponseModel:
    # Retrieve and print the session ID
    session_id = request.state.session_id
    print(f"[Session ID: {session_id}] Processing question: {body.question[:50]}...")

    # Store user message in chat memory
    chat_memory.add_message(session_id, "user", body.question)
    session_state = agent_chat_memory.get(session_id, {"messages": [], "documents": []})
    session_state["messages"] = session_state["messages"] + [
        ChatMessage.from_user(body.question)
    ]
    # Get conversation context for RAG
    conversation_context = chat_memory.get_context_for_rag(session_id, max_history=4)

    # Normalize sources
    sources = body.sources or []

    # Seed agent state with documents from previous turn for multi-turn tool chaining
    result = pipelines["agent"].run(
        messages=session_state["messages"],
        documents=session_state.get("documents", []),
    )
    print(result)
    # Convert source documents to typed metadata dicts for storage
    sources_dict = [
        _map_metadata(doc.meta).model_dump() for doc in result.get("documents", [])
    ]

    # Store assistant response with sources in chat memory
    chat_memory.add_message(
        session_id, "assistant", result["last_message"].text, sources_dict
    )
    agent_chat_memory[session_id] = {
        "messages": result["messages"],
        "documents": result.get("documents", []),
    }

    return {
        "answer": result["last_message"].text,
        "source_documents": sources_dict,
    }


@app.get("/chat/history")
async def get_chat_history(request: Request):
    """
    Retrieve chat history for the current session.
    Used when frontend reloads to restore conversation.
    """
    session_id = request.state.session_id
    history = chat_memory.get_history(session_id)

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "sources": msg.sources,
            }
            for msg in history
        ],
    }


@app.post("/chat/clear")
async def clear_chat_history(request: Request):
    """
    Clear chat history for the current session.
    """
    session_id = request.state.session_id
    chat_memory.clear_session(session_id)
    agent_chat_memory.pop(session_id, None)
    print(f"[Session ID: {session_id}] Chat history cleared")

    return {"status": "cleared", "session_id": session_id}


@app.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(limit: int = 100) -> GraphResponse:
    """
    Fetch the knowledge graph with nodes and their REFERENCES relationships from Neo4j.

    Args:
        limit: Maximum number of nodes to return (default: 100)
    """
    nodes, edges = pipelines["graph"].fetch_graph(limit=limit)
    return GraphResponse(nodes=nodes, edges=edges)


@app.get("/graph/stats")
async def get_graph_stats():
    """
    Get statistics about relationships in the knowledge graph.
    """
    stats = pipelines["graph"].get_relationship_stats()
    return {"relationships": stats}


@app.get("/graph/document/{doc_id}")
async def get_document_relationships(doc_id: str, depth: int = 1) -> GraphResponse:
    """
    Fetch a document and its related documents up to a certain depth.

    Args:
        doc_id: Element ID of the document node
        depth: How many relationship hops to traverse (default: 1, max: 3)
    """
    depth = min(max(1, depth), 3)  # Clamp between 1 and 3
    nodes, edges = pipelines["graph"].fetch_document_relationships(doc_id, depth)
    return GraphResponse(nodes=nodes, edges=edges)


@app.get("/icon")
async def get_icon(type: DocumentSourceType):
    # Map types to filenames
    filename = None
    if type == DocumentSourceType.JIRA:
        filename = "jira.png"
    elif type == DocumentSourceType.CONFLUENCE:
        filename = "confluence.png"
    elif type == DocumentSourceType.GITHUB:
        filename = "github.png"

    if not filename:
        raise HTTPException(status_code=404, detail="Icon not found")

    # Assets are stored next to this module in the `assets/` folder
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "assets", filename)

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Icon not found")

    # Return the file with an explicit image media type and disable caching
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(path, media_type="image/png", headers=headers)
