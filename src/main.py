import os

from dotenv import load_dotenv

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


from neo4j_haystack import (
    Neo4jDocumentStore,
    Neo4jClientConfig,
    Neo4jDynamicDocumentRetriever,
)

from src.common.models import DocumentSourceType, ResponseModel, GraphResponse
from src.core.knowledge_index import KnowledgeIndex
from src.core.question_answering import QuestionAnswering
from src.core.knowledge_graph_service import KnowledgeGraphService

from src.core.atlassian.jira_loader import JiraLoader
from src.core.atlassian.confluence_loader import ConfluenceLoader
from src.core.git.github_loader import GitHubLoader

from src.core.settings import (
    create_llm_generator,
    create_text_embedder,
    create_document_embedder,
)

load_dotenv()

pipelines = {}
loaders = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init loaders
    loaders["jira"] = JiraLoader(
        url=os.getenv("JIRA_URL"),
        username=os.getenv("JIRA_USERNAME"),
        api_key=os.getenv("JIRA_API_KEY"),
        projects=os.getenv("JIRA_PROJECTS").split(","),
    )
    loaders["confluence"] = ConfluenceLoader(
        url=os.getenv("CONFLUENCE_URL"),
        username=os.getenv("CONFLUENCE_USERNAME"),
        api_key=os.getenv("CONFLUENCE_API_KEY"),
        spaces=os.getenv("CONFLUENCE_SPACES").split(","),
    )
    loaders["github"] = GitHubLoader(
        repositories=os.getenv("GITHUB_REPOSITORIES", "").split(","),
        ref=os.getenv("GITHUB_REF", "main"),
        token=os.getenv("GITHUB_TOKEN"),
    )
    # Init RAG pipeline
    neo4j_document_store = Neo4jDocumentStore(
        url=os.getenv("NEO4J_URL"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database="neo4j",
        embedding_dim=int(os.getenv("EMBEDDING_DIMENSION", "768")),
        embedding_field="embedding",
        index="document_embeddings",  # The name of the Vector Index in Neo4j
        node_label="Document",
    )
    # Create a Neo4J component for hybrid search
    client_config = Neo4jClientConfig(
        url=os.getenv("NEO4J_URL"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    neo4j_embedding_retriever = Neo4jDynamicDocumentRetriever(
        client_config=client_config,
        runtime_parameters=["query_embedding"],
        doc_node_name="doc",
    )
    # Create provider components centrally
    llm_generator = create_llm_generator()
    text_embedder = create_text_embedder()
    document_embedder = create_document_embedder()

    pipelines["rag"] = QuestionAnswering(
        embedding_retriever=neo4j_embedding_retriever,
        llm_generator=llm_generator,
        text_embedder=text_embedder,
        index_name=os.getenv("NEO4J_INDEX", "document_embeddings"),
        top_k=int(os.getenv("NEO4J_TOP_K", "5")),
    )
    pipelines["index"] = KnowledgeIndex(
        document_store=neo4j_document_store, document_embedder=document_embedder
    )
    pipelines["graph"] = KnowledgeGraphService(
        neo4j_url=os.getenv("NEO4J_URL"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j")
    )
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

@app.post("/ask", response_model=ResponseModel)
async def answer_question(body: AskRequest) -> ResponseModel:
    # Normalize sources
    sources = body.sources or []

    result = pipelines["rag"].answer_question(body.question, sources)
    return result

@app.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph() -> GraphResponse:
    """
    Fetch the knowledge graph with nodes and their relationships from Neo4j.
    """
    nodes, edges = pipelines["graph"].fetch_graph(limit=100)
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
