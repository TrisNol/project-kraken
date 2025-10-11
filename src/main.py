import os

from dotenv import load_dotenv

from contextlib import asynccontextmanager
from fastapi import FastAPI

from haystack.document_stores.in_memory import InMemoryDocumentStore

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
    in_memory_document_store = InMemoryDocumentStore(
        embedding_similarity_function="cosine"
    )
    pipelines["rag"] = QuestionAnswering(document_store=in_memory_document_store)
    pipelines["index"] = KnowledgeIndex(document_store=in_memory_document_store)
    yield
    # Clean up before shutdown
    pipelines.clear()


app = FastAPI(lifespan=lifespan)


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

@app.post("/ask", response_model=ResponseModel)
async def answer_question(question: str) -> ResponseModel:
    result = pipelines["rag"].answer_question(question)
    return result
