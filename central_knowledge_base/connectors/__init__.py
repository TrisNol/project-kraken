"""Base connector interface and common functionality."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator, Optional
from datetime import datetime
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class Document(BaseModel):
    """Represents a document from any data source."""
    id: str
    title: str
    content: str
    source: str
    source_type: str  # confluence, jira, git
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    author: Optional[str] = None
    metadata: Dict[str, Any] = {}

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class Entity(BaseModel):
    """Represents an entity extracted from documents."""
    name: str
    type: str  # person, project, component, etc.
    description: Optional[str] = None
    source_documents: List[str] = []
    metadata: Dict[str, Any] = {}


class Relationship(BaseModel):
    """Represents a relationship between entities."""
    source_entity: str
    target_entity: str
    relationship_type: str
    confidence: float = 1.0
    source_documents: List[str] = []
    metadata: Dict[str, Any] = {}


class ConnectorResult(BaseModel):
    """Result from a connector operation."""
    documents: List[Document] = []
    entities: List[Entity] = []
    relationships: List[Relationship] = []
    metadata: Dict[str, Any] = {}


class BaseConnector(ABC):
    """Base class for all data source connectors."""
    
    def __init__(self, config: Any):
        """Initialize connector with configuration."""
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the connection to the data source is working."""
        pass
    
    @abstractmethod
    def fetch_documents(self, **kwargs) -> Iterator[Document]:
        """Fetch documents from the data source."""
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Get the source type identifier."""
        pass
    
    def extract_entities(self, documents: List[Document]) -> List[Entity]:
        """Extract entities from documents. Override for source-specific extraction."""
        entities = []
        for doc in documents:
            # Basic entity extraction - can be enhanced with NLP
            entities.extend(self._extract_basic_entities(doc))
        return entities
    
    def extract_relationships(self, entities: List[Entity], documents: List[Document]) -> List[Relationship]:
        """Extract relationships between entities. Override for source-specific extraction."""
        # Basic relationship extraction - can be enhanced
        return self._extract_basic_relationships(entities, documents)
    
    def _extract_basic_entities(self, document: Document) -> List[Entity]:
        """Basic entity extraction implementation."""
        entities = []
        
        # Extract author as person entity
        if document.author:
            entities.append(Entity(
                name=document.author,
                type="person",
                description=f"Author of {document.title}",
                source_documents=[document.id]
            ))
        
        # Add document itself as content entity
        entities.append(Entity(
            name=document.title,
            type="document",
            description=document.content[:200] + "..." if len(document.content) > 200 else document.content,
            source_documents=[document.id],
            metadata=document.metadata
        ))
        
        return entities
    
    def _extract_basic_relationships(self, entities: List[Entity], documents: List[Document]) -> List[Relationship]:
        """Basic relationship extraction implementation."""
        relationships = []
        
        # Create author -> document relationships
        doc_map = {doc.id: doc for doc in documents}
        entity_map = {e.name: e for e in entities}
        
        for entity in entities:
            if entity.type == "document" and entity.source_documents:
                doc_id = entity.source_documents[0]
                doc = doc_map.get(doc_id)
                if doc and doc.author and doc.author in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc.author,
                        target_entity=entity.name,
                        relationship_type="authored",
                        source_documents=[doc_id]
                    ))
        
        return relationships
    
    def sync(self, **kwargs) -> ConnectorResult:
        """Sync data from the source and return structured result."""
        self.logger.info(f"Starting sync for {self.get_source_type()}")
        
        documents = list(self.fetch_documents(**kwargs))
        entities = self.extract_entities(documents)
        relationships = self.extract_relationships(entities, documents)
        
        result = ConnectorResult(
            documents=documents,
            entities=entities,
            relationships=relationships,
            metadata={
                "source_type": self.get_source_type(),
                "sync_time": datetime.now().isoformat(),
                "document_count": len(documents),
                "entity_count": len(entities),
                "relationship_count": len(relationships)
            }
        )
        
        self.logger.info(f"Sync completed: {len(documents)} documents, {len(entities)} entities, {len(relationships)} relationships")
        return result