from haystack import Pipeline, component
from haystack.components.builders import ChatPromptBuilder
from haystack.dataclasses import ChatMessage
from typing import List

from src.common.models import BaseMetadata, ConfluenceMetadata, JiraMetadata, GitHubMetadata, ResponseModel
from src.core.settings import create_llm_generator


@component
class ChatMessageToText:
    """Converts a list of ChatMessage to a single text string."""
    
    @component.output_types(text=str)
    def run(self, replies: List[ChatMessage]) -> dict:
        """Extract text from the first ChatMessage in the list."""
        if not replies:
            return {"text": ""}
        return {"text": replies[0].text}


class QuestionAnswering:
    rag_pipeline: Pipeline = None

    def __init__(self, embedding_retriever, llm_generator, text_embedder):
        # Query rewriting template - converts follow-up questions to standalone queries
        query_rewrite_template = [
            ChatMessage.from_user(
                """Given a conversation history and a follow-up question, rewrite the question to be a standalone question that can be understood without the conversation context.

{% if conversation_history %}
Conversation History:
{{ conversation_history }}
{% endif %}

Follow-up Question: {{ question }}

Rewritten Standalone Question:"""
            )
        ]

        # Answer generation template
        answer_template = [
            ChatMessage.from_user(
                """
                Given the following information, answer the question.
                Consider only the context provided and do not make up any answers.
                Think about your answer carefully and provide a concise and accurate response.
                Ignore context that is not relevant to the question.
                Respond in the same language as the question.
                Format your answer in markdown without wrapping the entire response in markdown.

                If the context provided does not contain the answer, respond with "I don't know. Have you tried turning it off and on again?".

                {% if conversation_history %}
                {{ conversation_history }}
                
                {% endif %}
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

        # Create query rewriter component
        query_rewriter = ChatPromptBuilder(
            template=query_rewrite_template,
            required_variables={"question"}
        )
        
        # Create answer prompt builder
        answer_prompt_builder = ChatPromptBuilder(
            template=answer_template, required_variables={"documents", "question"}
        )

        # Create a separate LLM instance for query rewriting
        query_rewrite_llm = create_llm_generator()
        
        # Create text extractor to convert ChatMessage to string
        text_extractor = ChatMessageToText()

        basic_rag_pipeline = Pipeline()
        # Add components to pipeline
        basic_rag_pipeline.add_component("query_rewriter", query_rewriter)
        basic_rag_pipeline.add_component("query_rewrite_llm", query_rewrite_llm)
        basic_rag_pipeline.add_component("text_extractor", text_extractor)
        basic_rag_pipeline.add_component("text_embedder", text_embedder)
        basic_rag_pipeline.add_component("retriever", retriever)
        basic_rag_pipeline.add_component("answer_prompt_builder", answer_prompt_builder)
        basic_rag_pipeline.add_component("answer_llm", llm_generator)

        # Connect components
        # Query rewriting path
        basic_rag_pipeline.connect("query_rewriter.prompt", "query_rewrite_llm.messages")
        basic_rag_pipeline.connect("query_rewrite_llm.replies", "text_extractor.replies")
        basic_rag_pipeline.connect("text_extractor.text", "text_embedder.text")
        # Retrieval and answer generation path
        basic_rag_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        basic_rag_pipeline.connect("retriever", "answer_prompt_builder.documents")
        basic_rag_pipeline.connect("answer_prompt_builder.prompt", "answer_llm.messages")
        
        self.rag_pipeline = basic_rag_pipeline

    def answer_question(self, question: str, sources: list[str] | None = None, conversation_history: str = "") -> ResponseModel:
        # Prepare filters for the retriever
        filters = None
        if sources:
            filters = {"type": sources}

        response = self.rag_pipeline.run(
            {
                "query_rewriter": {
                    "question": question,
                    "conversation_history": conversation_history
                },
                "answer_prompt_builder": {
                    "question": question,
                    "conversation_history": conversation_history
                },
                "retriever": {"filters": filters},
            },
            include_outputs_from=["answer_llm", "retriever", "query_rewrite_llm"],
        )
        
        # Log the rewritten query for debugging
        rewritten_query = response.get("query_rewrite_llm", {}).get("replies", [{}])[0]
        if hasattr(rewritten_query, 'text'):
            print(f"[Query Rewrite] Original: {question[:50]}... -> Rewritten: {rewritten_query.text[:100]}...")
        
        response_text = response.get("answer_llm", {}).get("replies")[0].text
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
