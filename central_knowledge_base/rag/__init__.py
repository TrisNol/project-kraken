"""RAG (Retrieval-Augmented Generation) pipeline using LangGraph."""

from typing import List, Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass
import logging
from operator import add

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from central_knowledge_base.connectors import Document
from central_knowledge_base.graph import KnowledgeGraph
from central_knowledge_base.config import LLMConfig, VectorStoreConfig

logger = logging.getLogger(__name__)


class RAGState(TypedDict):
    """State for the RAG pipeline."""
    question: str
    retrieved_documents: Annotated[List[Document], add]
    retrieved_entities: Annotated[List[Dict[str, Any]], add]
    context: str
    answer: str
    metadata: Dict[str, Any]


@dataclass
class RAGResult:
    """Result from RAG query."""
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    context_used: str
    confidence: float
    metadata: Dict[str, Any]


class VectorStore:
    """Vector store for document embeddings."""
    
    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.client = None
        self.collection = None
        self.embedding_model = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize vector store and embedding model."""
        try:
            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(
                path=self.config.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(self.config.embedding_model)
            
            logger.info(f"Vector store initialized with {self.collection.count()} documents")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to vector store."""
        if not documents:
            return
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents_text = []
        
        for doc in documents:
            # Create text for embedding
            text_for_embedding = f"{doc.title}\n\n{doc.content}"
            
            # Compute embedding
            embedding = self.embedding_model.encode(text_for_embedding)
            
            ids.append(doc.id)
            embeddings.append(embedding.tolist())
            documents_text.append(text_for_embedding)
            
            # Prepare metadata (ChromaDB has limitations on metadata)
            metadata = {
                'title': doc.title[:1000],  # Limit length
                'source': doc.source,
                'source_type': doc.source_type,
                'author': doc.author or '',
                'url': doc.url or ''
            }
            
            # Add selected fields from original metadata
            if doc.metadata:
                for key in ['project_key', 'space_key', 'repo_name', 'issue_key']:
                    if key in doc.metadata:
                        metadata[key] = str(doc.metadata[key])
            
            metadatas.append(metadata)
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents_text,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to vector store")
    
    def search(self, query: str, top_k: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        # Compute query embedding
        query_embedding = self.embedding_model.encode(query)
        
        # Prepare where clause for filtering
        where_clause = None
        if filter_dict:
            where_clause = {}
            for key, value in filter_dict.items():
                if isinstance(value, list):
                    where_clause[key] = {"$in": value}
                else:
                    where_clause[key] = value
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_clause,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        search_results = []
        for i in range(len(results['ids'][0])):
            search_results.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i],
                'relevance_score': 1 - results['distances'][0][i]  # Convert distance to relevance
            })
        
        return search_results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return {
            'total_documents': self.collection.count(),
            'embedding_model': self.config.embedding_model
        }


class RAGPipeline:
    """RAG pipeline orchestrated with LangGraph."""
    
    def __init__(
        self,
        llm_config: LLMConfig,
        vector_store: VectorStore,
        knowledge_graph: KnowledgeGraph
    ):
        self.llm_config = llm_config
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.llm = self._initialize_llm()
        self.workflow = self._build_workflow()
    
    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize the language model."""
        return ChatOpenAI(
            model=self.llm_config.model,
            api_key=self.llm_config.api_key,
            temperature=self.llm_config.temperature,
            max_tokens=self.llm_config.max_tokens
        )
    
    def _build_workflow(self) -> StateGraph:
        """Build the RAG workflow using LangGraph."""
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("retrieve_documents", self._retrieve_documents)
        workflow.add_node("retrieve_entities", self._retrieve_entities)
        workflow.add_node("build_context", self._build_context)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Define the flow
        workflow.set_entry_point("retrieve_documents")
        workflow.add_edge("retrieve_documents", "retrieve_entities")
        workflow.add_edge("retrieve_entities", "build_context")
        workflow.add_edge("build_context", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        return workflow.compile()
    
    def _retrieve_documents(self, state: RAGState) -> RAGState:
        """Retrieve relevant documents from vector store."""
        question = state["question"]
        
        # Search for relevant documents
        search_results = self.vector_store.search(question, top_k=5)
        
        # Convert search results back to Document objects
        retrieved_documents = []
        for result in search_results:
            # Reconstruct document from stored data
            metadata = result['metadata']
            doc = Document(
                id=result['id'],
                title=metadata.get('title', ''),
                content=result['document'],
                source=metadata.get('source', ''),
                source_type=metadata.get('source_type', ''),
                url=metadata.get('url'),
                author=metadata.get('author'),
                metadata={
                    'relevance_score': result['relevance_score'],
                    'distance': result['distance']
                }
            )
            retrieved_documents.append(doc)
        
        logger.info(f"Retrieved {len(retrieved_documents)} documents for question: {question}")
        
        return {
            **state,
            "retrieved_documents": retrieved_documents,
            "metadata": {
                **state.get("metadata", {}),
                "documents_retrieved": len(retrieved_documents)
            }
        }
    
    def _retrieve_entities(self, state: RAGState) -> RAGState:
        """Retrieve relevant entities from knowledge graph."""
        question = state["question"]
        retrieved_documents = state["retrieved_documents"]
        
        # Extract entity names mentioned in retrieved documents
        mentioned_entities = set()
        for doc in retrieved_documents:
            for entity_name in self.knowledge_graph.entities.keys():
                if entity_name.lower() in doc.content.lower():
                    mentioned_entities.add(entity_name)
        
        # Get entity details and relationships
        retrieved_entities = []
        for entity_name in list(mentioned_entities)[:10]:  # Limit to 10 entities
            entity = self.knowledge_graph.entities.get(entity_name)
            if entity:
                # Get entity neighbors for additional context
                neighbors = self.knowledge_graph.get_entity_neighbors(entity_name, max_depth=1)
                
                retrieved_entities.append({
                    'name': entity.name,
                    'type': entity.type,
                    'description': entity.description,
                    'neighbors': neighbors,
                    'metadata': entity.metadata
                })
        
        logger.info(f"Retrieved {len(retrieved_entities)} entities for question: {question}")
        
        return {
            **state,
            "retrieved_entities": retrieved_entities,
            "metadata": {
                **state.get("metadata", {}),
                "entities_retrieved": len(retrieved_entities)
            }
        }
    
    def _build_context(self, state: RAGState) -> RAGState:
        """Build context from retrieved documents and entities."""
        retrieved_documents = state["retrieved_documents"]
        retrieved_entities = state["retrieved_entities"]
        
        context_parts = []
        
        # Add document context
        if retrieved_documents:
            context_parts.append("## Relevant Documents:")
            for i, doc in enumerate(retrieved_documents[:3]):  # Use top 3 documents
                context_parts.append(f"\n### Document {i+1}: {doc.title}")
                context_parts.append(f"Source: {doc.source_type}")
                if doc.author:
                    context_parts.append(f"Author: {doc.author}")
                if doc.url:
                    context_parts.append(f"URL: {doc.url}")
                
                # Truncate content to avoid token limits
                content = doc.content[:1500] + "..." if len(doc.content) > 1500 else doc.content
                context_parts.append(f"Content: {content}")
        
        # Add entity context
        if retrieved_entities:
            context_parts.append("\n\n## Relevant Entities:")
            for entity in retrieved_entities[:5]:  # Use top 5 entities
                context_parts.append(f"\n### {entity['name']} ({entity['type']})")
                if entity['description']:
                    context_parts.append(f"Description: {entity['description']}")
                
                # Add relationship context
                neighbors = entity.get('neighbors', {})
                if neighbors:
                    relationships = []
                    for node_name, node_data in neighbors.items():
                        for neighbor_info in node_data.get('neighbors', []):
                            rel_type = neighbor_info['relationship']
                            neighbor_name = neighbor_info['entity']
                            direction = neighbor_info['direction']
                            
                            if direction == 'outgoing':
                                relationships.append(f"{node_name} --{rel_type}--> {neighbor_name}")
                            else:
                                relationships.append(f"{neighbor_name} --{rel_type}--> {node_name}")
                    
                    if relationships:
                        context_parts.append(f"Related to: {', '.join(relationships[:3])}")
        
        context = '\n'.join(context_parts)
        
        return {
            **state,
            "context": context
        }
    
    def _generate_answer(self, state: RAGState) -> RAGState:
        """Generate answer using the language model."""
        question = state["question"]
        context = state["context"]
        
        # Build prompt
        system_prompt = """You are an expert assistant that helps answer questions using a knowledge base that includes data from Confluence, Jira, Git repositories, and other sources.

Use the provided context to answer the user's question. Be specific and cite the sources when possible. If the context doesn't contain enough information to answer the question, say so clearly.

Focus on:
1. Directly answering the question
2. Providing relevant details from the context
3. Citing specific sources (documents, people, projects, etc.)
4. Explaining relationships between different pieces of information when relevant

Context:
{context}"""
        
        user_prompt = f"Question: {question}"
        
        # Create messages
        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=user_prompt)
        ]
        
        # Generate response
        response = self.llm.invoke(messages)
        answer = response.content
        
        logger.info(f"Generated answer for question: {question}")
        
        return {
            **state,
            "answer": answer,
            "metadata": {
                **state.get("metadata", {}),
                "context_length": len(context),
                "answer_length": len(answer)
            }
        }
    
    def query(self, question: str) -> RAGResult:
        """Execute RAG pipeline to answer a question."""
        logger.info(f"Processing RAG query: {question}")
        
        # Initialize state
        initial_state = RAGState(
            question=question,
            retrieved_documents=[],
            retrieved_entities=[],
            context="",
            answer="",
            metadata={}
        )
        
        # Execute workflow
        final_state = self.workflow.invoke(initial_state)
        
        # Extract sources information
        sources = []
        for doc in final_state["retrieved_documents"]:
            sources.append({
                'title': doc.title,
                'source_type': doc.source_type,
                'url': doc.url,
                'relevance_score': doc.metadata.get('relevance_score', 0),
                'author': doc.author
            })
        
        # Calculate confidence based on relevance scores
        confidence = 0.0
        if sources:
            confidence = sum(s.get('relevance_score', 0) for s in sources) / len(sources)
        
        result = RAGResult(
            question=question,
            answer=final_state["answer"],
            sources=sources,
            context_used=final_state["context"],
            confidence=confidence,
            metadata=final_state["metadata"]
        )
        
        logger.info(f"RAG query completed with confidence: {confidence:.2f}")
        return result