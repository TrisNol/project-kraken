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

from src.tools.atlassian_mcp import atlassian_mcp_tool
from src.tools.github_mcp import github_mcp_tool

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

    main_kraken_agent = SoftwareDeveloperAgent(
        chat_generator=container.llm_generator(),
        tools=[
            atlassian_mcp_tool,
            github_mcp_tool,
        ],
        streaming_callback=print_streaming_chunk if container.config.app.environment() == "development" else None,
    )
    pipelines["agent"] = main_kraken_agent

    yield

    # Clean up before shutdown
    atlassian_mcp_tool.close()
    github_mcp_tool.close()
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
