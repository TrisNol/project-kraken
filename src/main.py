import os
import uuid
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from haystack.dataclasses import ChatMessage
from haystack.tools import ComponentTool
from haystack.components.generators.utils import print_streaming_chunk
from starlette.middleware.base import BaseHTTPMiddleware

from src.agents import SoftwareDeveloperAgent
from src.common.models import (
    DocumentSourceType,
    ResponseModel,
    GraphResponse,
    BaseMetadata,
    JiraMetadata,
    ConfluenceMetadata,
    GitHubMetadata,
)
from src.core.chat_memory import ChatMemory
from src.config import AppContainer, load_env_config
from src.tools.utils import _docs_to_summary
from src.tools.filter_docs_tool import FilterDocs

logger = logging.getLogger(__name__)

pipelines = {}
loaders = {}
chat_memory = ChatMemory(max_messages_per_session=50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container: AppContainer = app.container

    # Init loaders
    loaders["jira"] = container.jira_loader()
    loaders["confluence"] = container.confluence_loader()
    loaders["github"] = container.github_loader()

    pipelines["index"] = container.knowledge_index()
    pipelines["graph"] = container.knowledge_graph_service()

    rag_tool = ComponentTool(
        component=container.rag_search(),
        name="rag_search_tool",
        description="Semantic search across all indexed documents (Jira, Confluence, GitHub). Use this for broad or conceptual questions where the user describes a topic, problem, or concept in natural language (e.g. 'How does our authentication flow work?', 'What is the deployment process?').",
        inputs_from_state={"allowed_sources": "allowed_sources"},
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    graph_query_tool = ComponentTool(
        component=container.graph_query(),
        name="graph_query_tool",
        description="Direct property lookup in the knowledge graph. Use this when the user mentions a specific identifier such as a Jira ticket key (e.g. 'DEV-42'), a Confluence space key, a project key, a GitHub repo name, or a file path. Fast and precise — best for targeted lookups by known names or keys.",
        inputs_from_state={"allowed_sources": "allowed_sources"},
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
        component=container.fetch_neighbors(),
        name="fetch_neighbors_tool",
        description="Expand context by fetching documents linked to the ones already retrieved via REFERENCES relationships in the graph. Use this AFTER an initial search when the user asks about related items, dependencies, or you need more surrounding context (e.g. 'What tickets are related to DEV-42?', 'Show me linked Confluence pages').",
        inputs_from_state={
            "documents": "documents",
            "allowed_sources": "allowed_sources",
        },
        outputs_to_state={"documents": {"source": "documents"}},
        outputs_to_string={"source": "documents", "handler": _docs_to_summary},
    )

    main_kraken_agent = SoftwareDeveloperAgent(
        chat_generator=container.llm_generator(),
        tools=[
            rag_tool,
            graph_query_tool,
            filter_docs_tool,
            fetch_neighbors_tool,
        ],
        streaming_callback=print_streaming_chunk if container.config.app.environment() == "development" else None,
    )
    pipelines["agent"] = main_kraken_agent

    yield
    # Clean up before shutdown
    pipelines.clear()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.container = AppContainer()
    app.container.config.from_dict(load_env_config())
    return app


app = create_app()
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
    return {"status": "index cleared"}


from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str
    sources: list[str] = Field(default_factory=list)


def _normalize_requested_sources(sources: list[str] | None) -> list[str]:
    if not sources:
        return []

    allowed_values = {source.value for source in DocumentSourceType}
    normalized: list[str] = []
    for source in sources:
        source_value = source.strip().upper()
        if not source_value:
            continue
        if source_value not in allowed_values:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid source '{source}'. "
                    f"Allowed values: {', '.join(sorted(allowed_values))}"
                ),
            )
        if source_value not in normalized:
            normalized.append(source_value)
    return normalized


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
    logger.info(f"[Session ID: {session_id}] Received question: {body.question} with sources: {body.sources}")

    # Store user message in chat memory
    chat_memory.add_message(session_id, "user", body.question)

    allowed_sources = _normalize_requested_sources(body.sources)

    session_state = chat_memory.get_agent_state(session_id)
    session_documents = session_state.get("documents", [])
    if allowed_sources:
        session_documents = [
            doc
            for doc in session_documents
            if str(doc.meta.get("type", "")).upper() in allowed_sources
        ]

    session_messages = session_state["messages"] + [ChatMessage.from_user(body.question)]

    # Seed agent state with documents from previous turn for multi-turn tool chaining
    result = pipelines["agent"].run(
        messages=session_messages,
        documents=session_documents,
        allowed_sources=allowed_sources,
    )

    result_documents = result.get("documents", [])
    if allowed_sources:
        result_documents = [
            doc
            for doc in result_documents
            if str(doc.meta.get("type", "")).upper() in allowed_sources
        ]

    # Convert source documents to typed metadata dicts for storage
    sources_dict = [
        _map_metadata(doc.meta).model_dump() for doc in result_documents
    ]

    # Store assistant response with sources in chat memory
    chat_memory.add_message(
        session_id, "assistant", result["last_message"].text, sources_dict
    )
    chat_memory.set_agent_state(
        session_id,
        messages=result["messages"],
        documents=result_documents,
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
    logger.info(f"[Session ID: {session_id}] Chat history cleared")

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
