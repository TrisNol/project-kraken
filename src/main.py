import os

from dotenv import load_dotenv

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from neo4j_haystack import Neo4jDocumentStore, Neo4jEmbeddingRetriever

from src.common.models import ResponseModel
from src.core.knowledge_index import KnowledgeIndex
from src.core.question_answering import QuestionAnswering

from src.core.atlassian.jira_loader import JiraLoader
from src.core.atlassian.confluence_loader import ConfluenceLoader
from src.core.git.github_loader import GitHubLoader

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
        projects=os.getenv("JIRA_PROJECTS"),
        limit=50,
    )
    loaders["confluence"] = ConfluenceLoader(
        url=os.getenv("CONFLUENCE_URL"),
        username=os.getenv("CONFLUENCE_USERNAME"),
        api_key=os.getenv("CONFLUENCE_API_KEY"),
        space_key=os.getenv("CONFLUENCE_SPACES"),
        include_attachments=False,
        limit=50,
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
        embedding_dim=768,
        embedding_field="embedding",
        index="document_embeddings", # The name of the Vector Index in Neo4j
        node_label="Document",
    )
    neo4j_embedding_retriever = Neo4jEmbeddingRetriever(
        document_store=neo4j_document_store,
        top_k=5,
    )
    pipelines["rag"] = QuestionAnswering(embedding_retriever=neo4j_embedding_retriever)
    pipelines["index"] = KnowledgeIndex(document_store=neo4j_document_store)
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

@app.post("/ask", response_model=ResponseModel)
async def answer_question(question: str) -> ResponseModel:
    result = pipelines["rag"].answer_question(question)
    return result
