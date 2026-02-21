# Document/Chunk Architecture Refactoring

## Overview
The knowledge base has been refactored to implement a two-tier persistence model in Neo4j:
- **Document nodes**: Hold metadata and relationships between documents
- **Chunk nodes**: Hold content and embeddings, reference parent documents

This separation provides clearer semantics and better performance for both graph visualization and semantic search.

## System Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        Jira[Jira API]
        Confluence[Confluence API]
        GitHub[GitHub API]
    end
    
    subgraph "Backend - Python/FastAPI"
        subgraph "Loaders"
            JL[JiraLoader]
            CL[ConfluenceLoader]
            GL[GitHubLoader]
        end
        
        subgraph "Processing Pipeline"
            DS[DocumentSplitter]
            DE[DocumentEmbedder]
        end
        
        subgraph "Persistence Layer"
            DCW[DocumentChunkWriter]
            RM[RelationshipManager]
        end
        
        subgraph "Query Layer"
            CR[ChunkRetriever]
            QA[QuestionAnswering]
            GS[KnowledgeGraphService]
        end
        
        API[FastAPI Endpoints]
    end
    
    subgraph "Storage"
        Neo4j[(Neo4j Graph DB)]
        Ollama[Ollama LLM]
    end
    
    subgraph "Frontend - Angular"
        UI[User Interface]
        Chat[Chat Component]
        Graph[Graph Component]
    end
    
    Jira --> JL
    Confluence --> CL
    GitHub --> GL
    
    JL --> DS
    CL --> DS
    GL --> DS
    
    DS --> DE
    DE --> DCW
    DCW --> Neo4j
    
    JL -.links.-> RM
    CL -.links.-> RM
    GL -.links.-> RM
    RM --> Neo4j
    
    API --> QA
    API --> GS
    QA --> CR
    CR --> Neo4j
    QA --> Ollama
    GS --> Neo4j
    
    UI --> Chat
    UI --> Graph
    Chat --> API
    Graph --> API
    
    style Neo4j fill:#4caf50,stroke:#2e7d32,stroke-width:3px,color:#fff
    style Ollama fill:#ff9800,stroke:#e65100,stroke-width:2px,color:#fff
    style API fill:#2196f3,stroke:#0d47a1,stroke-width:2px,color:#fff
```

## Architecture

### Node Structure

```mermaid
graph TB
    subgraph "Document Node"
        D["Document<br/>id: jira:PROJ-123<br/>type: JIRA<br/>metadata..."]
    end
    
    subgraph "Chunk Nodes"
        C1["Chunk 0<br/>content: text...<br/>embedding: [...]<br/>chunk_index: 0"]
        C2["Chunk 1<br/>content: text...<br/>embedding: [...]<br/>chunk_index: 1"]
        C3["Chunk N<br/>content: text...<br/>embedding: [...]<br/>chunk_index: N"]
    end
    
    subgraph "Related Documents"
        D2["Document<br/>id: confluence:456"]
        D3["Document<br/>id: jira:PROJ-124"]
    end
    
    C1 -->|PART_OF<br/>chunk_index: 0| D
    C2 -->|PART_OF<br/>chunk_index: 1| D
    C3 -->|PART_OF<br/>chunk_index: N| D
    D -->|REFERENCES| D2
    D -->|REFERENCES| D3
    
    style D fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    style D2 fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    style D3 fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    style C1 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style C2 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style C3 fill:#fff3e0,stroke:#e65100,stroke-width:2px
```

#### Document Nodes
- **Label**: `Document`
- **Properties**:
  - `id`: Unique identifier (e.g., `jira:PROJ-123`, `confluence:12345`, `github:repo:path/to/file.py`)
  - `type`: Document type (`JIRA`, `CONFLUENCE`, `GITHUB`)
  - Additional metadata specific to each type (issue_key, page_id, repo_name, etc.)
  - **NO embeddings or content**
- **Relationships**:
  - `REFERENCES`: Points to other Document nodes
  - `PART_OF` (incoming): Receives references from Chunk nodes

#### Chunk Nodes
- **Label**: `Chunk`
- **Properties**:
  - `id`: Hash-based unique identifier
  - `content`: Text content of the chunk
  - `embedding`: Vector embedding (768 dimensions)
  - `chunk_index`: Position of chunk within parent document (0-based)
- **Relationships**:
  - `PART_OF`: Points to parent Document node, includes `chunk_index` property for ordering
- **Index**:
  - Vector index `chunk_embeddings` on `embedding` property

### Data Flow

#### Indexing Flow

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant Loaders as Data Loaders<br/>(Jira/Confluence/GitHub)
    participant Splitter as DocumentSplitter
    participant Embedder as DocumentEmbedder
    participant Writer as DocumentChunkWriter
    participant RelMgr as RelationshipManager
    participant Neo4j as Neo4j Database
    
    API->>Loaders: load()
    Loaders->>Loaders: Extract links metadata
    Loaders-->>API: Documents with links
    
    API->>Splitter: split(documents)
    Splitter-->>API: Chunks
    
    API->>Embedder: embed(chunks)
    Embedder-->>API: Chunks with embeddings
    
    API->>Writer: write(chunks)
    Writer->>Writer: Group by document
    Writer->>Neo4j: CREATE Document nodes
    Writer->>Neo4j: CREATE Chunk nodes
    Writer->>Neo4j: CREATE PART_OF relationships
    Writer-->>API: Success
    
    API->>RelMgr: create_relationships(documents)
    RelMgr->>Neo4j: MATCH Document by id
    RelMgr->>Neo4j: CREATE REFERENCES relationships
    RelMgr-->>API: Statistics
```

#### Query Flow

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant QA as QuestionAnswering
    participant TextEmb as TextEmbedder
    participant Retriever as ChunkRetriever
    participant Neo4j as Neo4j Database
    participant LLM as LLM Generator
    
    User->>API: POST /ask {question}
    API->>QA: answer_question(question)
    
    QA->>TextEmb: embed(question)
    TextEmb-->>QA: embedding vector
    
    QA->>Retriever: run(query_embedding)
    Retriever->>Neo4j: Vector search on chunk_embeddings
    Neo4j-->>Retriever: Top K Chunks
    Retriever->>Neo4j: MATCH (chunk)-[:PART_OF]->(doc)
    Neo4j-->>Retriever: Chunks + Document metadata
    Retriever-->>QA: Documents (chunk content + doc metadata)
    
    QA->>LLM: generate(prompt + documents)
    LLM-->>QA: Answer
    QA-->>API: ResponseModel
    API-->>User: Answer + source documents
```

#### Graph Visualization Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Angular Frontend
    participant API as FastAPI
    participant GraphSvc as KnowledgeGraphService
    participant Neo4j as Neo4j Database
    
    User->>Frontend: Navigate to graph view
    Frontend->>API: GET /graph?limit=100
    API->>GraphSvc: fetch_graph(limit)
    
    GraphSvc->>Neo4j: MATCH (d:Document) RETURN d
    Neo4j-->>GraphSvc: Document nodes
    
    GraphSvc->>Neo4j: MATCH (s:Document)-[r:REFERENCES]->(t:Document)
    Neo4j-->>GraphSvc: Relationships + nodes
    
    GraphSvc-->>API: GraphResponse(nodes, edges)
    API-->>Frontend: {nodes: [...], edges: [...]}
    
    Frontend->>Frontend: Render with FFlow
    Frontend-->>User: Interactive graph visualization
```

## Key Components

### DocumentChunkWriter
**Path**: `src/core/document_chunk_writer.py`

Creates the two-tier structure in Neo4j:
- Groups chunks by parent document
- Creates Document nodes with metadata (no embeddings)
- Creates Chunk nodes with content, embeddings, and chunk_index
- Links chunks to documents with PART_OF relationship (including chunk_index on relationship)
- Ensures `chunk_embeddings` vector index exists

### ChunkRetriever
**Path**: `src/core/chunk_retriever.py`

Custom retriever for embedding-based search:
- Queries `chunk_embeddings` vector index
- Traverses PART_OF relationship to parent Document
- Returns chunk content with document metadata
- Supports filtering by document type

### KnowledgeIndex
**Path**: `src/core/knowledge_index.py`

Orchestrates the indexing process:
- Uses DocumentChunkWriter instead of Neo4jDocumentStore
- Creates relationships between Documents (not Chunks)
- Provides stats about Documents and Chunks

### RelationshipManager
**Path**: `src/core/relationship_manager.py`

Creates REFERENCES edges between Document nodes:
- Uses LIMIT 1 to prevent duplicates
- Supports Jira ↔ Jira, Jira ↔ Confluence, GitHub ↔ * relationships
- Works with document IDs, not chunk IDs

### KnowledgeGraphService
**Path**: `src/core/knowledge_graph_service.py`

Fetches graph data for visualization:
- Returns Document nodes only (not Chunks)
- Returns REFERENCES relationships
- Provides relationship statistics

## Benefits

### 1. Clear Semantics
- Documents represent logical entities (issues, pages, files)
- Chunks are implementation details for embedding search
- Graph visualization shows documents, not technical chunks

### 2. Reduced Duplication
- One Document node per document (instead of N chunks labeled as "Document")
- REFERENCES relationships between documents (not N×M between all chunks)
- Metadata stored once per document

### 3. Better Performance
- Embedding search targets Chunks (smaller nodes, focused purpose)
- Graph queries target Documents (no need to deduplicate chunks)
- Relationship creation simpler (one edge per document pair)

### 4. Easier Maintenance
- Clear separation of concerns
- Simpler queries (no need for LIMIT 1 workarounds on chunks)
- More intuitive data model

## Migration Notes

### Breaking Changes
1. **Neo4j Schema**: Existing `Document` nodes will coexist with new structure
   - Old nodes: Haystack documents (chunks) labeled as `Document`
   - New nodes: Logical documents labeled as `Document` + chunks labeled as `Chunk`
   - **Action**: Clear database before re-indexing

2. **Vector Index**: Changed from `document_embeddings` to `chunk_embeddings`
   - Old index: Points to old Document nodes
   - New index: Points to Chunk nodes
   - **Action**: Drop old index or use different database

3. **Environment Variables**: Update `NEO4J_INDEX` to `chunk_embeddings`

### Backward Compatibility
- No breaking changes in API endpoints
- Frontend requires no changes
- Query responses maintain same structure

## Configuration

### Environment Variables
```bash
# Vector index name for chunks (default: chunk_embeddings)
NEO4J_INDEX=chunk_embeddings

# Embedding dimension (default: 768)
EMBEDDING_DIMENSION=768

# Top K results for retrieval (default: 5)
NEO4J_TOP_K=5
```

### Neo4j Indexes
The system automatically creates:
- `chunk_embeddings`: Vector index on Chunk.embedding (cosine similarity)

## Testing

### Verify Structure
```cypher
// Check Document nodes
MATCH (d:Document)
RETURN count(d) as documents, collect(DISTINCT d.type) as types

// Check Chunk nodes
MATCH (c:Chunk)
RETURN count(c) as chunks

// Check relationships with ordering
MATCH (c:Chunk)-[r:PART_OF]->(d:Document)
RETURN count(*) as part_of_edges, 
       min(r.chunk_index) as min_index, 
       max(r.chunk_index) as max_index

// Verify chunk ordering for a specific document
MATCH (c:Chunk)-[r:PART_OF]->(d:Document)
WHERE d.id = 'jira:PROJ-123'
RETURN c.chunk_index, substring(c.content, 0, 100) as preview
ORDER BY c.chunk_index

MATCH (d1:Document)-[:REFERENCES]->(d2:Document)
RETURN count(*) as reference_edges

// Verify chunks have embeddings
MATCH (c:Chunk)
WHERE c.embedding IS NOT NULL
RETURN count(c) as chunks_with_embeddings
```

### Test Retrieval
```python
# Query should return chunks with document metadata
from src.core.chunk_retriever import ChunkRetriever

retriever = ChunkRetriever(
    neo4j_url="bolt://localhost:7687",
    neo4j_username="neo4j",
    neo4j_password="password",
    index_name="chunk_embeddings",
    top_k=5
)

# Example embedding (replace with actual embedding)
results = retriever.run(query_embedding=[0.1] * 768)
for doc in results["documents"]:
    print(f"Content: {doc.content[:100]}...")
    print(f"Type: {doc.meta['type']}")
    print(f"Score: {doc.meta['score']}")
```

## Future Enhancements

1. **Reconstruct Full Documents**: Add endpoint to retrieve all chunks in order and reconstruct original document
2. **Smart Chunking**: Use content-aware chunking strategies
3. **Chunk Overlap**: Track overlapping chunks for better context
4. **Hybrid Search**: Combine vector search with keyword search on chunks
5. **Document Versioning**: Track document versions and changes over time

## Chat History & Session Management Implementation

### Session Tracking Architecture

**SessionMiddleware** (`src/main.py`):
- Implements Starlette `BaseHTTPMiddleware`
- Checks for existing `X-Session-ID` in request cookies
- Generates UUID v4 if no session exists
- Stores session ID in `request.state.session_id` for endpoint access
- Sets HTTP-only cookie with:
  - 30-day expiration (`max_age=86400 * 30`)
  - `samesite="lax"` for CSRF protection
  - `secure=False` (set to `True` in production with HTTPS)
- Also adds `X-Session-ID` response header for visibility

### In-Memory Chat Storage

**ChatMemory Component** (`src/core/chat_memory.py`):

**Data Structures**:
```python
class ChatHistoryMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    sources: Optional[List[Dict[str, Any]]]  # Full source metadata

class ChatMemory:
    _memory: Dict[str, List[ChatHistoryMessage]]  # session_id -> messages
    _lock: Lock  # Thread-safe operations
    max_messages_per_session: int  # Default: 50
```

**Key Methods**:
- `add_message(session_id, role, content, sources)`: Store message with optional sources
- `get_history(session_id, limit)`: Retrieve conversation history
- `get_context_for_rag(session_id, max_history)`: Format history for LLM context
- `clear_session(session_id)`: Remove all messages for a session
- `get_session_count()`: Get total active sessions

**Thread Safety**:
All operations use `self._lock` to ensure concurrent request safety.

**Memory Management**:
Automatic FIFO truncation when `max_messages_per_session` exceeded:
```python
if len(self._memory[session_id]) > self.max_messages_per_session:
    self._memory[session_id] = self._memory[session_id][-self.max_messages_per_session:]
```

### Conversational RAG Pipeline

**Query Rewriting Architecture**:

The RAG pipeline implements a two-stage LLM approach:

1. **Query Rewriting Stage**: Converts contextual questions to standalone queries
2. **Answer Generation Stage**: Generates final answer with full context

**Pipeline Components** (`src/core/question_answering.py`):

```mermaid
graph LR
    Q[Question] --> QR[Query Rewriter]
    CH[Chat History] --> QR
    QR --> RLLM[Rewrite LLM]
    RLLM --> TE[Text Extractor]
    TE --> Emb[Text Embedder]
    Emb --> Ret[Retriever]
    Ret --> Docs[Documents]
    Docs --> APB[Answer Prompt]
    Q --> APB
    CH --> APB
    APB --> ALLM[Answer LLM]
    ALLM --> Ans[Answer]
```

### Security & Privacy

**Session Isolation**:
- Each session ID is a cryptographically random UUID
- No cross-session data access
- Session-scoped storage prevents user data mixing

**Cookie Security**:
- `httponly=True`: Prevents JavaScript access (XSS protection)
- `samesite="lax"`: CSRF protection
- Should enable `secure=True` in production (HTTPS only)

**Data Lifecycle**:
- Sessions persist only in application memory
- Application restart clears all history
- No persistent storage of conversations (privacy by design)
- Users can manually clear via `/chat/clear` endpoint
