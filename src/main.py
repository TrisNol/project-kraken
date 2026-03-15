import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from haystack.tools import ComponentTool
from haystack.components.generators.utils import print_streaming_chunk
from starlette.middleware.base import BaseHTTPMiddleware

from src.agents import SoftwareDeveloperAgent
from src.api import api_router
from src.core.chat_memory import ChatMemory
from src.config import AppContainer, load_env_config
from src.tools.utils import _docs_to_summary
from src.tools.filter_docs_tool import FilterDocs

@asynccontextmanager
async def lifespan(app: FastAPI):
    container: AppContainer = app.container
    loaders = app.state.loaders
    pipelines = app.state.pipelines

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
    loaders.clear()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.container = AppContainer()
    app.container.config.from_dict(load_env_config())
    app.state.pipelines = {}
    app.state.loaders = {}
    app.state.chat_memory = ChatMemory(max_messages_per_session=50)
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

app.include_router(api_router)
