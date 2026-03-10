from typing import List
from haystack import Document, Document, Pipeline, component


@component
class RAGSearch:

    def __init__(self, embedding_retriever, text_embedder):
        pipeline = Pipeline()

        pipeline.add_component("text_embedder", text_embedder)
        pipeline.add_component("retriever", embedding_retriever)

        pipeline.connect("text_embedder.embedding", "retriever.query_embedding")

        self.rag_pipeline = pipeline

    @component.output_types(documents=List[Document])
    def run(self, query: str) -> dict:
        result = self.rag_pipeline.run({"text_embedder": {"text": query}})
        return {"documents": result["retriever"]["documents"]}
