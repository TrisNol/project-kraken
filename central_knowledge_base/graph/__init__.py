"""Knowledge graph construction and management."""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import networkx as nx
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

from central_knowledge_base.connectors import Document, Entity, Relationship
from central_knowledge_base.config import GraphConfig

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Knowledge graph for storing and querying entities and relationships."""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.graph = nx.MultiDiGraph()
        self.documents: Dict[str, Document] = {}
        self.entities: Dict[str, Entity] = {}
        self.embeddings_model = None
        self.entity_embeddings: Dict[str, np.ndarray] = {}
        
        # Ensure persist directory exists
        Path(config.persist_directory).mkdir(parents=True, exist_ok=True)
    
    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to the knowledge graph."""
        for doc in documents:
            self.documents[doc.id] = doc
            logger.debug(f"Added document: {doc.id}")
    
    def add_entities(self, entities: List[Entity]) -> None:
        """Add entities to the knowledge graph."""
        for entity in entities:
            self.entities[entity.name] = entity
            
            # Add entity as node to graph
            self.graph.add_node(
                entity.name,
                type=entity.type,
                description=entity.description,
                source_documents=entity.source_documents,
                metadata=entity.metadata
            )
            logger.debug(f"Added entity: {entity.name} ({entity.type})")
    
    def add_relationships(self, relationships: List[Relationship]) -> None:
        """Add relationships to the knowledge graph."""
        for rel in relationships:
            # Add edge to graph
            self.graph.add_edge(
                rel.source_entity,
                rel.target_entity,
                relationship_type=rel.relationship_type,
                confidence=rel.confidence,
                source_documents=rel.source_documents,
                metadata=rel.metadata
            )
            logger.debug(f"Added relationship: {rel.source_entity} --{rel.relationship_type}--> {rel.target_entity}")
    
    def compute_entity_embeddings(self) -> None:
        """Compute embeddings for entities to enable similarity search."""
        if not self.entities:
            logger.warning("No entities to compute embeddings for")
            return
        
        if self.embeddings_model is None:
            logger.info("Loading embedding model")
            self.embeddings_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # Prepare texts for embedding
        entity_texts = []
        entity_names = []
        
        for name, entity in self.entities.items():
            # Create text representation of entity
            text_parts = [entity.name]
            
            if entity.description:
                text_parts.append(entity.description)
            
            # Add context from source documents
            if entity.source_documents and len(entity.source_documents) <= 3:
                for doc_id in entity.source_documents:
                    doc = self.documents.get(doc_id)
                    if doc:
                        # Add truncated content
                        content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                        text_parts.append(content_preview)
            
            text = " ".join(text_parts)
            entity_texts.append(text)
            entity_names.append(name)
        
        # Compute embeddings
        logger.info(f"Computing embeddings for {len(entity_texts)} entities")
        embeddings = self.embeddings_model.encode(entity_texts)
        
        # Store embeddings
        for name, embedding in zip(entity_names, embeddings):
            self.entity_embeddings[name] = embedding
        
        logger.info("Entity embeddings computed successfully")
    
    def find_similar_entities(self, entity_name: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Find entities similar to the given entity."""
        if entity_name not in self.entity_embeddings:
            return []
        
        target_embedding = self.entity_embeddings[entity_name]
        similarities = []
        
        for name, embedding in self.entity_embeddings.items():
            if name != entity_name:
                similarity = cosine_similarity([target_embedding], [embedding])[0][0]
                similarities.append((name, float(similarity)))
        
        # Sort by similarity and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def discover_implicit_relationships(self) -> List[Relationship]:
        """Discover implicit relationships between entities based on similarity and context."""
        implicit_relationships = []
        
        if not self.entity_embeddings:
            logger.warning("No embeddings available for relationship discovery")
            return implicit_relationships
        
        # Find similar entities that might be related
        for entity_name in self.entities:
            similar_entities = self.find_similar_entities(entity_name, top_k=5)
            
            for similar_name, similarity in similar_entities:
                if similarity > self.config.similarity_threshold:
                    # Check if entities share documents
                    entity1 = self.entities[entity_name]
                    entity2 = self.entities[similar_name]
                    
                    shared_docs = set(entity1.source_documents).intersection(set(entity2.source_documents))
                    
                    if shared_docs:
                        # Create implicit relationship
                        relationship = Relationship(
                            source_entity=entity_name,
                            target_entity=similar_name,
                            relationship_type="similar_to",
                            confidence=similarity,
                            source_documents=list(shared_docs),
                            metadata={'discovered': True, 'similarity_score': similarity}
                        )
                        implicit_relationships.append(relationship)
        
        logger.info(f"Discovered {len(implicit_relationships)} implicit relationships")
        return implicit_relationships
    
    def get_entity_neighbors(self, entity_name: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get neighboring entities within specified depth."""
        if entity_name not in self.graph:
            return {}
        
        neighbors = {}
        visited = set()
        current_level = {entity_name}
        
        for depth in range(max_depth):
            next_level = set()
            
            for node in current_level:
                if node in visited:
                    continue
                
                visited.add(node)
                node_neighbors = []
                
                # Get outgoing edges
                for neighbor in self.graph.successors(node):
                    edge_data = self.graph.get_edge_data(node, neighbor)
                    for key, data in edge_data.items():
                        node_neighbors.append({
                            'entity': neighbor,
                            'relationship': data.get('relationship_type', 'unknown'),
                            'confidence': data.get('confidence', 1.0),
                            'direction': 'outgoing'
                        })
                        next_level.add(neighbor)
                
                # Get incoming edges
                for predecessor in self.graph.predecessors(node):
                    edge_data = self.graph.get_edge_data(predecessor, node)
                    for key, data in edge_data.items():
                        node_neighbors.append({
                            'entity': predecessor,
                            'relationship': data.get('relationship_type', 'unknown'),
                            'confidence': data.get('confidence', 1.0),
                            'direction': 'incoming'
                        })
                        next_level.add(predecessor)
                
                if node_neighbors:
                    neighbors[node] = {
                        'depth': depth,
                        'neighbors': node_neighbors,
                        'entity_data': self.entities.get(node, {})
                    }
            
            current_level = next_level
        
        return neighbors
    
    def find_path(self, source_entity: str, target_entity: str, max_length: int = 4) -> List[List[str]]:
        """Find paths between two entities."""
        if source_entity not in self.graph or target_entity not in self.graph:
            return []
        
        try:
            # Find all simple paths up to max_length
            paths = list(nx.all_simple_paths(
                self.graph, 
                source=source_entity, 
                target=target_entity, 
                cutoff=max_length
            ))
            return paths[:10]  # Limit to first 10 paths
        except nx.NetworkXNoPath:
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        entity_types = defaultdict(int)
        relationship_types = defaultdict(int)
        source_types = defaultdict(int)
        
        for entity in self.entities.values():
            entity_types[entity.type] += 1
        
        for _, _, data in self.graph.edges(data=True):
            relationship_types[data.get('relationship_type', 'unknown')] += 1
        
        for doc in self.documents.values():
            source_types[doc.source_type] += 1
        
        return {
            'total_documents': len(self.documents),
            'total_entities': len(self.entities),
            'total_relationships': self.graph.number_of_edges(),
            'entity_types': dict(entity_types),
            'relationship_types': dict(relationship_types),
            'source_types': dict(source_types),
            'graph_density': nx.density(self.graph),
            'connected_components': nx.number_weakly_connected_components(self.graph),
            'has_embeddings': len(self.entity_embeddings) > 0
        }
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save knowledge graph to disk."""
        if filename is None:
            filename = 'knowledge_graph.pkl'
        
        filepath = Path(self.config.persist_directory) / filename
        
        data = {
            'graph': self.graph,
            'documents': self.documents,
            'entities': self.entities,
            'entity_embeddings': self.entity_embeddings,
            'config': self.config
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"Knowledge graph saved to {filepath}")
        
        # Also save as JSON for inspection (without embeddings)
        json_filepath = filepath.with_suffix('.json')
        json_data = {
            'statistics': self.get_statistics(),
            'entities': [entity.dict() for entity in self.entities.values()],
            'documents_summary': [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'source_type': doc.source_type,
                    'content_length': len(doc.content)
                }
                for doc in self.documents.values()
            ]
        }
        
        with open(json_filepath, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
    
    def load(self, filename: Optional[str] = None) -> bool:
        """Load knowledge graph from disk."""
        if filename is None:
            filename = 'knowledge_graph.pkl'
        
        filepath = Path(self.config.persist_directory) / filename
        
        if not filepath.exists():
            logger.warning(f"Knowledge graph file not found: {filepath}")
            return False
        
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            self.graph = data['graph']
            self.documents = data['documents']
            self.entities = data['entities']
            self.entity_embeddings = data.get('entity_embeddings', {})
            
            logger.info(f"Knowledge graph loaded from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading knowledge graph: {e}")
            return False