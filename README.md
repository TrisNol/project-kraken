# Central Knowledge Base

A RAG (Retrieval-Augmented Generation) application based on LangGraph/LangChain that integrates with external data sources to create a comprehensive knowledge graph for efficient information retrieval and question answering.

## Features

- **Multi-Source Data Ingestion**: Connects to Confluence, Jira, Git repositories, and more
- **Knowledge Graph Construction**: Automatically identifies and maps relationships between data entities
- **RAG Pipeline**: Combines retrieval and generation using state-of-the-art LLMs
- **LangGraph Integration**: Orchestrates complex workflows for data processing and retrieval
- **Semantic Search**: Advanced embedding-based search capabilities
- **RESTful API**: Easy integration with existing systems

## Architecture

The system consists of several key components:

1. **Connectors**: Modular connectors for different data sources (Confluence, Jira, Git)
2. **Knowledge Graph**: Graph-based representation of entities and their relationships
3. **Vector Store**: Efficient similarity search using embeddings
4. **RAG Pipeline**: LangGraph-orchestrated retrieval and generation workflow
5. **API Layer**: FastAPI-based REST interface

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

1. Copy the example configuration:
```bash
cp config/config.example.yaml config/config.yaml
```

2. Configure your data sources and API keys in `config/config.yaml`

3. Run the application:
```bash
ckb run
```

4. Access the API at `http://localhost:8000`

## Configuration

See `config/config.example.yaml` for configuration options including:
- Data source credentials
- LLM settings
- Vector store configuration
- Graph database settings

## API Usage

### Query the Knowledge Base
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "What are the current open issues in project X?"}'
```

### Ingest Data
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
     -H "Content-Type: application/json" \
     -d '{"source": "confluence", "space_key": "PROJ"}'
```

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black .
```

Type checking:
```bash
mypy central_knowledge_base
```

## License

Apache License 2.0
