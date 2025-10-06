import os
from dotenv import load_dotenv

from haystack import Pipeline
from haystack.document_stores.types import DocumentStore
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaChatGenerator
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever

load_dotenv()

class QuestionAnswering:
    rag_pipeline: Pipeline = None

    def __init__(self, document_store: DocumentStore):
        template = [
            ChatMessage.from_user(
                """
                Given the following information, answer the question.

                Context:
                {% for document in documents %}
                    {{ document.content }}
                {% endfor %}

                Question: {{question}}
                Answer:
                """
            )
        ]
        llm_generator = OllamaChatGenerator(
            model=os.getenv("LLM_CHAT_MODEL"),
            url=os.getenv("LLM_HOST"),
        )
        text_embedder = OllamaTextEmbedder(
            model=os.getenv("LLM_EMBEDDING_MODEL"),
            url=os.getenv("LLM_HOST"),
        )
        retriever = InMemoryEmbeddingRetriever(document_store)

        prompt_builder = ChatPromptBuilder(
            template=template,
            required_variables={"documents", "question"}
        )

        basic_rag_pipeline = Pipeline()
        # Add components to your pipeline
        basic_rag_pipeline.add_component("text_embedder", text_embedder)
        basic_rag_pipeline.add_component("retriever", retriever)
        basic_rag_pipeline.add_component("prompt_builder", prompt_builder)
        basic_rag_pipeline.add_component("llm", llm_generator)

        basic_rag_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        basic_rag_pipeline.connect("retriever", "prompt_builder.documents")
        basic_rag_pipeline.connect("prompt_builder", "llm")

        self.rag_pipeline = basic_rag_pipeline

        print(basic_rag_pipeline.graph)

    def answer_question(self, question: str):
        response = self.rag_pipeline.run(
            {
                "text_embedder": {"text": question},
                "prompt_builder": {"question": question},
            },
            include_outputs_from=[
                "llm",
                "retriever"
            ]
        )
        print(response)
        return {
            "answer": response.get("llm", {}).get("replies", ["I'm sorry, I don't know how to answer this."])[0],
            "documents": [doc.content for doc in response.get("retriever", {}).get("documents", [])],
        }
