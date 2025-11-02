from haystack import Document, Pipeline
from haystack.document_stores.types import DocumentStore
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.preprocessors import DocumentSplitter

class KrakenDocumentSplitter(DocumentSplitter):
    def split(self, document: Document):
        meta_type = document.meta.get("type", "")

        if meta_type == "Confluence":
            # Split at chapters with an overlap
            return self.split_markdown_chapters_with_overlap(document)
        elif meta_type == "Jira":
            # Split at chapters without overlap
            return self.split_markdown_chapters(document)
        elif meta_type == "GitHub":
            # Only split if really necessary
            return self.split_if_necessary(document)
        else:
            # Default splitting behavior
            return super().split(document)

    def split_markdown_chapters_with_overlap(self, document: Document):
        # Custom logic to split markdown chapters with overlap
        chapters = document.content.split("\n# ")  # Split by markdown chapter headers
        overlap = 1  # Example: Overlap of 1 chapter
        split_documents = []

        for i in range(len(chapters)):
            start = max(0, i - overlap)
            end = i + 1
            content = "\n# ".join(chapters[start:end])
            split_documents.append(Document(content=content, meta=document.meta))

        return split_documents

    def split_markdown_chapters(self, document: Document):
        # Custom logic to split markdown chapters without overlap
        chapters = document.content.split("\n# ")  # Split by markdown chapter headers
        split_documents = [
            Document(content=f"# {chapter}" if idx > 0 else chapter, meta=document.meta)
            for idx, chapter in enumerate(chapters)
        ]
        return split_documents

    def split_if_necessary(self, document: Document):
        # Custom logic to split only if necessary
        max_length = 1000  # Example threshold
        if len(document.content) > max_length:
            midpoint = len(document.content) // 2
            return [
                Document(content=document.content[:midpoint], meta=document.meta),
                Document(content=document.content[midpoint:], meta=document.meta),
            ]
        return [document]

class KnowledgeIndex:
    indexing_pipeline: Pipeline = None

    def __init__(self, document_store: DocumentStore, document_embedder):
        writer = DocumentWriter(document_store=document_store)
        splitter = KrakenDocumentSplitter()
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
        # Filter out documents with less than 50 characters
        documents = [d for d in documents if getattr(d, "content", None) and len(str(d.content)) >= 50]
        if not documents:
            return
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
