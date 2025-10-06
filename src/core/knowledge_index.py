import os
from dotenv import load_dotenv

from haystack import Document, Pipeline
from haystack_integrations.components.embedders.ollama.document_embedder import (
    OllamaDocumentEmbedder,
)
from haystack.document_stores.types import DocumentStore
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.preprocessors import DocumentSplitter

load_dotenv()


class KnowledgeIndex:
    indexing_pipeline: Pipeline = None

    def __init__(self, document_store: DocumentStore = None):
        # Init Pipeline components
        document_embedder = OllamaDocumentEmbedder(
            model=os.getenv("LLM_EMBEDDING_MODEL"),
            url=os.getenv("LLM_HOST"),
        )
        writer = DocumentWriter(document_store=document_store)
        splitter = DocumentSplitter()
        writer = DocumentWriter(
            document_store=document_store, policy=DuplicatePolicy.OVERWRITE
        )

        # Construct pipeline
        self.indexing_pipeline = Pipeline()
        self.indexing_pipeline.add_component("splitter", splitter)
        self.indexing_pipeline.add_component("embedder", document_embedder)
        self.indexing_pipeline.add_component("writer", writer)
        self.indexing_pipeline.connect("splitter", "embedder")
        self.indexing_pipeline.connect("embedder", "writer")

    def create_index(self, documents: list[Document]):
        self.indexing_pipeline.run({"documents": documents})

    def get_index_stats(self):
        if not self.indexing_pipeline:
            return {}
        document_store: DocumentStore = self.indexing_pipeline.get_component(
            "writer"
        ).document_store
        return document_store.count_documents()

    def clear_index(self):
        if self.indexing_pipeline:
            document_store: DocumentStore = self.indexing_pipeline.get_component(
                "writer"
            ).document_store
            document_store.delete_documents([])
