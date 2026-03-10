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

    from src.tools.rag_search_tool import RAGSearch

    rag_tool = ComponentTool(
        component=RAGSearch(
            embedding_retriever=chunk_retriever,
            text_embedder=text_embedder,
        ),
        name="rag_search_tool",
        description="Search in the central RAG index containing informations of various sources.",
        outputs_to_state={"documents": {"source": "documents"}},
    )

    kraken_agent = Agent(
        chat_generator=OpenAIChatGenerator(model="gpt-4o-mini"),
        system_prompt="""
        You are Project Kraken, an AI assistant built on-top off a central knowledge base containing information about an enterprise's documentation, processes, and data.
        You will have access to a mulititude of tools containing different sets of informations, and your task is to use these tools to answer user questions as accurately as possible.
        Always use the tools at your disposal to find the most accurate and up-to-date information, and only answer questions based on the information you find in the tools. Do not make up answers or hallucinate information that is not present in the tools. 
        If you cannot find the answer to a question using the tools at your disposal, respond with a follow-up question asking for more information or clarification from the user.
        """,
        tools=[
            rag_tool  # Search through the vector DB --> Extend with filters for documents types
            # graph_query_tool # Search through the knowledge graph/vector DB for documuments using cypher queries --> fast lookup with information retrieved from the users' text input
            # filter_docs_tool # Using the documents currently in scope, filter out irrelevant documents based on the user's question to narrow down the context and information available for answering the question
            # fetch_neighbors_tool # Using the documents currently in scope, fetch related documents from the graph to expand the context and information available for answering the question
        ],
        state_schema={"documents": {"type": list}},
        streaming_callback=print_streaming_chunk,
        max_agent_steps=3
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

    # Get conversation context for RAG
    conversation_context = chat_memory.get_context_for_rag(session_id, max_history=4)

    # Normalize sources
    sources = body.sources or []

    result = pipelines["agent"].run(
        messages=[ChatMessage.from_user(body.question)],
    )
    print(result)
    # Convert source documents to typed metadata dicts for storage
    sources_dict = [_map_metadata(doc.meta).model_dump() for doc in result["documents"]]

    # Store assistant response with sources in chat memory
    chat_memory.add_message(
        session_id, "assistant", result["last_message"].text, sources_dict
    )

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
