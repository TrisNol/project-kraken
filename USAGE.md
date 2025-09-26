# Usage Guide - Central Knowledge Base

This guide walks you through setting up and using the Central Knowledge Base RAG application.

## Prerequisites

- Python 3.9 or higher
- Git
- Access to external data sources (Confluence, Jira, Git repositories)
- OpenAI API key (or other supported LLM provider)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/TrisNol/central-knowledge-base.git
cd central-knowledge-base
```

### 2. Install Dependencies

```bash
pip install -e .
```

Or for development:
```bash
pip install -e ".[dev]"
```

### 3. Set Up Configuration

Copy the example configuration file:
```bash
cp config/config.example.yaml config/config.yaml
```

Copy the environment template:
```bash
cp .env.example .env
```

## Configuration

### Environment Variables

Edit `.env` with your actual credentials:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# Confluence Configuration
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net
CONFLUENCE_USERNAME=your.email@company.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# Jira Configuration  
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_API_TOKEN=your-jira-api-token

# Git Configuration (optional for public repos)
GITHUB_ACCESS_TOKEN=ghp_your-github-token-here
```

### Configuration File

Edit `config/config.yaml` to specify which spaces, projects, and repositories to sync:

```yaml
confluence:
  enabled: true
  spaces:
    - "PROJ"    # Your Confluence space keys
    - "DOCS"
    - "TEAM"

jira:
  enabled: true
  projects:
    - "PROJ"    # Your Jira project keys
    - "DEV"

git:
  enabled: true
  repositories:
    - "https://github.com/yourorg/repo1"
    - "https://github.com/yourorg/repo2"
```

## Getting Started

### 1. Test Connections

First, verify your configuration by testing connections to external sources:

```bash
ckb test
```

Expected output:
```
Connection Test Results:
  confluence: ✓ Connected
  jira: ✓ Connected
  git: ✓ Connected
```

### 2. Sync Data

Sync data from all configured sources:

```bash
ckb sync
```

Or sync from specific sources:
```bash
ckb sync --sources confluence jira
```

This will:
- Fetch documents from your configured sources
- Extract entities and relationships
- Build a knowledge graph
- Create vector embeddings for semantic search
- Save everything to local storage

### 3. Query the Knowledge Base

Ask questions using the CLI:

```bash
ckb query "What is Project Alpha?"
ckb query "What bugs are assigned to Mike Johnson?"
ckb query "Which repositories use React?"
```

### 4. Start the API Server

Launch the REST API server:

```bash
ckb run
```

The server will start at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive API documentation.

## Using the API

### Query Endpoint

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "What are the current open issues in project X?"}'
```

Response:
```json
{
  "question": "What are the current open issues in project X?",
  "answer": "Based on the available information, there are currently 3 open issues in project X...",
  "sources": [
    {
      "title": "[PROJ-123] Authentication Bug",
      "source_type": "jira",
      "url": "https://company.atlassian.net/browse/PROJ-123",
      "relevance_score": 0.87
    }
  ],
  "confidence": 0.82
}
```

### Ingest Data

Trigger data synchronization via API:

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
     -H "Content-Type: application/json" \
     -d '{"source": "confluence", "parameters": {"spaces": ["PROJ"]}}'
```

### Get Statistics

```bash
curl "http://localhost:8000/stats"
```

## Advanced Usage

### Custom Queries with Filters

```bash
# Query with source type filter
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Authentication issues", 
       "filters": {"source_type": ["jira"]},
       "max_results": 10
     }'
```

### Entity Exploration

```bash
# List all entities
curl "http://localhost:8000/api/v1/entities"

# Get specific entity details
curl "http://localhost:8000/api/v1/entities/John%20Doe"
```

### CLI Statistics

```bash
ckb stats
```

Output:
```
Knowledge Graph Statistics:
  Documents: 1,247
  Entities: 324
  Relationships: 892
  Graph Density: 0.0234
  Connected Components: 12

Entity Types:
  person: 45
  project: 12
  component: 67
  document: 200

Relationship Types:
  authored: 234
  assigned_to: 89
  belongs_to: 156
  uses_component: 78
```

## Data Sources Configuration

### Confluence

The system fetches:
- Pages from specified spaces
- Page content (HTML converted to text)
- Metadata (author, creation date, labels)
- Automatically extracts mentioned users and projects

### Jira

The system fetches:
- Issues from specified projects
- Issue details (description, status, assignee, reporter)
- Comments (limited to first 10)
- Component and label information

### Git Repositories

The system processes:
- Source code files (various programming languages)
- Documentation files (Markdown, text)
- Commit history (configurable depth)
- File relationships and authorship

## Customization

### Adding New Connectors

1. Create a new connector class inheriting from `BaseConnector`
2. Implement required methods: `test_connection()`, `fetch_documents()`, `get_source_type()`
3. Optionally override entity and relationship extraction methods

```python
from central_knowledge_base.connectors import BaseConnector

class MyConnector(BaseConnector):
    def test_connection(self) -> bool:
        # Test connection logic
        return True
    
    def fetch_documents(self, **kwargs):
        # Fetch and yield documents
        yield Document(...)
    
    def get_source_type(self) -> str:
        return "my_source"
```

### Custom LLM Providers

Modify the LLM configuration in `config/config.yaml`:

```yaml
llm:
  provider: "custom"
  model: "my-custom-model"
  api_key: "${MY_API_KEY}"
  base_url: "https://my-llm-api.com"
```

## Troubleshooting

### Common Issues

1. **Connection timeouts**: Increase timeout values in connector configurations
2. **Memory issues with large repositories**: Reduce `max_files` and `max_commits` parameters
3. **API rate limits**: Add delays between API calls in connector implementations
4. **Embedding computation slow**: Consider using a smaller embedding model

### Logs

Enable debug logging:
```bash
ckb --verbose sync
```

### Health Check

Monitor system health:
```bash
curl "http://localhost:8000/health"
```

## Performance Optimization

### For Large Datasets

1. **Incremental sync**: The system tracks what's already processed
2. **Batch processing**: Process documents in chunks
3. **Selective sync**: Sync only specific spaces/projects/repos
4. **Embedding caching**: Embeddings are cached to avoid recomputation

### Resource Management

- Vector store: Uses persistent ChromaDB for efficient similarity search
- Knowledge graph: NetworkX graphs are serialized for fast loading
- Memory usage: Large documents are truncated during processing

## Security Considerations

- API keys are stored in environment variables, not in code
- Local data is stored in configurable directories
- No sensitive data is sent to external services except for LLM queries
- API endpoints can be secured with authentication (add middleware)

## Monitoring and Maintenance

### Regular Maintenance

1. **Data freshness**: Schedule regular syncs with cron
2. **Storage cleanup**: Monitor disk usage of vector store and graph data
3. **Performance monitoring**: Track query response times
4. **Health checks**: Monitor connector availability

### Backup

Important directories to backup:
- `./data/vectorstore/` - Vector embeddings
- `./data/graph/` - Knowledge graph data
- `config/` - Configuration files

## Integration Examples

### Slack Bot Integration

```python
from central_knowledge_base.rag import RAGPipeline
from central_knowledge_base.config import get_config

config = get_config()
# ... initialize components
rag = RAGPipeline(...)

@slack_app.message("ask")
def handle_question(message, say):
    result = rag.query(message['text'])
    say(result.answer)
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Update Knowledge Base
  run: |
    ckb sync --sources git
    ckb query "What changed in the last release?" > release-summary.md
```

This completes the comprehensive usage guide for the Central Knowledge Base system.