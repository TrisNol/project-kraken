"""FastAPI application for Central Knowledge Base."""

import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from central_knowledge_base.config import get_config, Config
from central_knowledge_base.connectors.confluence import ConfluenceConnector
from central_knowledge_base.connectors.jira import JiraConnector  
from central_knowledge_base.connectors.git import GitConnector
from central_knowledge_base.graph import KnowledgeGraph
from central_knowledge_base.rag import RAGPipeline, VectorStore

logger = logging.getLogger(__name__)


# Pydantic models for API
class QueryRequest(BaseModel):
    """Request model for knowledge base queries."""
    question: str = Field(..., description="Question to ask the knowledge base")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters for search")
    max_results: int = Field(5, description="Maximum number of results to return")


class QueryResponse(BaseModel):
    """Response model for knowledge base queries."""
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    metadata: Dict[str, Any]


class IngestRequest(BaseModel):
    """Request model for data ingestion."""
    source: str = Field(..., description="Data source (confluence, jira, git)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Source-specific parameters")


class IngestResponse(BaseModel):
    """Response model for data ingestion."""
    status: str
    message: str
    documents_processed: int
    entities_created: int
    relationships_created: int
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    components: Dict[str, str]


class StatsResponse(BaseModel):
    """Statistics response model."""
    knowledge_graph: Dict[str, Any]
    vector_store: Dict[str, Any]
    connectors: Dict[str, Any]


# Global application state
app_state = {
    'config': None,
    'knowledge_graph': None,
    'vector_store': None,
    'rag_pipeline': None,
    'connectors': {}
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Central Knowledge Base API")
    
    try:
        # Load configuration
        config = get_config()
        app_state['config'] = config
        
        # Initialize knowledge graph
        knowledge_graph = KnowledgeGraph(config.graph)
        knowledge_graph.load()  # Try to load existing graph
        app_state['knowledge_graph'] = knowledge_graph
        
        # Initialize vector store
        vector_store = VectorStore(config.vector_store)
        app_state['vector_store'] = vector_store
        
        # Initialize RAG pipeline
        rag_pipeline = RAGPipeline(config.llm, vector_store, knowledge_graph)
        app_state['rag_pipeline'] = rag_pipeline
        
        # Initialize connectors
        connectors = {}
        
        if config.confluence.enabled:
            try:
                confluece_connector = ConfluenceConnector(config.confluence)
                if confluece_connector.test_connection():
                    connectors['confluence'] = confluece_connector
                    logger.info("Confluence connector initialized")
                else:
                    logger.warning("Confluence connector failed connection test")
            except Exception as e:
                logger.warning(f"Failed to initialize Confluence connector: {e}")
        
        if config.jira.enabled:
            try:
                jira_connector = JiraConnector(config.jira)
                if jira_connector.test_connection():
                    connectors['jira'] = jira_connector
                    logger.info("Jira connector initialized")
                else:
                    logger.warning("Jira connector failed connection test")
            except Exception as e:
                logger.warning(f"Failed to initialize Jira connector: {e}")
        
        if config.git.enabled:
            try:
                git_connector = GitConnector(config.git)
                if git_connector.test_connection():
                    connectors['git'] = git_connector
                    logger.info("Git connector initialized")
                else:
                    logger.warning("Git connector failed connection test")
            except Exception as e:
                logger.warning(f"Failed to initialize Git connector: {e}")
        
        app_state['connectors'] = connectors
        
        logger.info("Central Knowledge Base API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Central Knowledge Base API")


# Create FastAPI app
app = FastAPI(
    title="Central Knowledge Base",
    description="A RAG application with LangGraph and external connectors",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Central Knowledge Base API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    components = {}
    
    # Check knowledge graph
    if app_state['knowledge_graph']:
        stats = app_state['knowledge_graph'].get_statistics()
        components['knowledge_graph'] = f"OK ({stats['total_entities']} entities, {stats['total_relationships']} relationships)"
    else:
        components['knowledge_graph'] = "ERROR"
    
    # Check vector store
    if app_state['vector_store']:
        stats = app_state['vector_store'].get_statistics()
        components['vector_store'] = f"OK ({stats['total_documents']} documents)"
    else:
        components['vector_store'] = "ERROR"
    
    # Check RAG pipeline
    components['rag_pipeline'] = "OK" if app_state['rag_pipeline'] else "ERROR"
    
    # Check connectors
    for name, connector in app_state['connectors'].items():
        components[f'connector_{name}'] = "OK" if connector else "ERROR"
    
    # Determine overall status
    status = "healthy" if all("OK" in status for status in components.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        version="0.1.0",
        components=components
    )


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """Get system statistics."""
    knowledge_graph_stats = {}
    if app_state['knowledge_graph']:
        knowledge_graph_stats = app_state['knowledge_graph'].get_statistics()
    
    vector_store_stats = {}
    if app_state['vector_store']:
        vector_store_stats = app_state['vector_store'].get_statistics()
    
    connector_stats = {}
    for name, connector in app_state['connectors'].items():
        connector_stats[name] = {
            'status': 'connected',
            'type': connector.get_source_type()
        }
    
    return StatsResponse(
        knowledge_graph=knowledge_graph_stats,
        vector_store=vector_store_stats,
        connectors=connector_stats
    )


@app.post("/api/v1/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """Query the knowledge base."""
    if not app_state['rag_pipeline']:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")
    
    try:
        # Execute RAG query
        result = app_state['rag_pipeline'].query(request.question)
        
        return QueryResponse(
            question=result.question,
            answer=result.answer,
            sources=result.sources,
            confidence=result.confidence,
            metadata=result.metadata
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_data(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingest data from external sources."""
    if request.source not in app_state['connectors']:
        raise HTTPException(status_code=400, detail=f"Connector '{request.source}' not available")
    
    # Run ingestion in background
    background_tasks.add_task(
        _perform_ingestion,
        request.source,
        request.parameters
    )
    
    return IngestResponse(
        status="started",
        message=f"Data ingestion from {request.source} started in background",
        documents_processed=0,
        entities_created=0,
        relationships_created=0,
        metadata={"source": request.source, "parameters": request.parameters}
    )


async def _perform_ingestion(source: str, parameters: Dict[str, Any]):
    """Perform data ingestion (background task)."""
    logger.info(f"Starting data ingestion from {source}")
    
    try:
        connector = app_state['connectors'][source]
        knowledge_graph = app_state['knowledge_graph']
        vector_store = app_state['vector_store']
        
        # Sync data from connector
        result = connector.sync(**parameters)
        
        # Add to knowledge graph
        knowledge_graph.add_documents(result.documents)
        knowledge_graph.add_entities(result.entities)
        knowledge_graph.add_relationships(result.relationships)
        
        # Discover implicit relationships
        implicit_relations = knowledge_graph.discover_implicit_relationships()
        knowledge_graph.add_relationships(implicit_relations)
        
        # Update embeddings
        knowledge_graph.compute_entity_embeddings()
        
        # Add documents to vector store
        vector_store.add_documents(result.documents)
        
        # Save knowledge graph
        knowledge_graph.save()
        
        logger.info(f"Ingestion completed: {len(result.documents)} documents, {len(result.entities)} entities, {len(result.relationships)} relationships")
        
    except Exception as e:
        logger.error(f"Error during ingestion from {source}: {e}")


@app.get("/api/v1/entities/{entity_name}")
async def get_entity(entity_name: str):
    """Get details about a specific entity."""
    if not app_state['knowledge_graph']:
        raise HTTPException(status_code=503, detail="Knowledge graph not initialized")
    
    entity = app_state['knowledge_graph'].entities.get(entity_name)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Get entity relationships
    neighbors = app_state['knowledge_graph'].get_entity_neighbors(entity_name, max_depth=2)
    
    # Get similar entities
    similar_entities = app_state['knowledge_graph'].find_similar_entities(entity_name, top_k=5)
    
    return {
        'entity': entity.dict(),
        'neighbors': neighbors,
        'similar_entities': similar_entities
    }


@app.get("/api/v1/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List entities with optional filtering."""
    if not app_state['knowledge_graph']:
        raise HTTPException(status_code=503, detail="Knowledge graph not initialized")
    
    entities = list(app_state['knowledge_graph'].entities.values())
    
    # Filter by type if specified
    if entity_type:
        entities = [e for e in entities if e.type == entity_type]
    
    # Apply pagination
    total = len(entities)
    entities = entities[offset:offset + limit]
    
    return {
        'entities': [e.dict() for e in entities],
        'total': total,
        'limit': limit,
        'offset': offset
    }


def create_app(config: Optional[Config] = None) -> FastAPI:
    """Create FastAPI application with optional config override."""
    if config:
        from central_knowledge_base.config import set_config
        set_config(config)
    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the FastAPI server."""
    uvicorn.run(
        "central_knowledge_base.api:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug"
    )