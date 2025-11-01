from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage

from src.common.models import BaseMetadata, ConfluenceMetadata, JiraMetadata, GitHubMetadata, ResponseModel


class QuestionAnswering:
    rag_pipeline: Pipeline = None

    def __init__(self, embedding_retriever, llm_generator, text_embedder):
        template = [
            ChatMessage.from_user(
                """
                Given the following information, answer the question.
                Respond in the same language as the question.
                Format your answer in markdown.

                Context:
                {% for document in documents %}
                    {{ document.content }}
                {% endfor %}

                Question: {{question}}
                Answer:
                """
            )
        ]
        retriever = embedding_retriever

        prompt_builder = ChatPromptBuilder(
            template=template, required_variables={"documents", "question"}
        )

        basic_rag_pipeline = Pipeline()
        # Add components to your pipeline
        basic_rag_pipeline.add_component("text_embedder", text_embedder)
        basic_rag_pipeline.add_component("retriever", retriever)
        basic_rag_pipeline.add_component("prompt_builder", prompt_builder)
        basic_rag_pipeline.add_component("llm", llm_generator)

        basic_rag_pipeline.connect(
            "text_embedder.embedding", "retriever.query_embedding"
        )
        basic_rag_pipeline.connect("retriever", "prompt_builder.documents")
        basic_rag_pipeline.connect("prompt_builder", "llm")

        self.rag_pipeline = basic_rag_pipeline

    def answer_question(self, question: str) -> ResponseModel:
        response = self.rag_pipeline.run(
            {
                "text_embedder": {"text": question},
                "prompt_builder": {"question": question},
            },
            include_outputs_from=["llm", "retriever"],
        )
        response_text = response.get("llm", {}).get("replies")[0].text
        return ResponseModel(
            answer=response_text,
            source_documents=[
                self.__map_metadata(doc.meta) for doc in response.get("retriever", {}).get("documents", [])
            ],
        )

    def __map_metadata(self, meta: dict) -> BaseMetadata:
        if meta.get("type") == "JIRA":
            return JiraMetadata(**meta)
        elif meta.get("type") == "CONFLUENCE":
            return ConfluenceMetadata(**meta)
        elif meta.get("type") == "GITHUB":
            return GitHubMetadata(**meta)
        else:
            raise ValueError(f"Unknown document type: {meta.get('type')}")
