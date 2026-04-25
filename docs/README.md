<img src="./images/project_kraken_landscape.png">

# Release the Kraken

Project Kraken is a **Central Knowledge Base** designed to bring together multiple sources of information:

- GitHub 
- Confluence
- Jira

into a single, unified platform.

With **Project Kraken**, you can:

- 🗂️ Access all your resources in one place
- 🤖 Perform Agentic Retrieval-Augmented Generation (Agentic RAG)
- 🚀 Boost productivity and collaboration across teams

Unleash the power of seamless knowledge integration with Project Kraken! 🦑

## Agentic RAG at a Glance

The runtime agent can dynamically combine these tools to generate an intelligent response to your query:

- **RAG Search Tool**: semantic retrieval over chunk embeddings
- **Graph Query Tool**: targeted Neo4j lookup using filters extracted from user prompts
- **Fetch Neighbors Tool**: graph neighborhood expansion via `REFERENCES` relationships
- **Filter Docs Tool**: post-retrieval pruning of weakly relevant documents

All retrieval tools support and respect source filters passed by the API request (for example: Jira-only, GitHub-only).

## Architecture Overview

```mermaid
graph LR
    subgraph "External Sources"
        J[📋 Jira]
        C[📄 Confluence]
        G[🔧 GitHub]
    end
    
    subgraph "Project Kraken"
        KB[🦑 Central Knowledge Base]
        Agent[🧠 Agentic RAG Agent]
        subgraph "🛠️ Tools"
            T1[🔍 RAG Search]
            T2[🗂️ Graph Query]
            T3[🕸️ Fetch Neighbors]
            T4[🔎 Filter Docs]
        end
        Graph[🕸️ Knowledge Graph]
    end
    
    subgraph "Features"
        Search[🔍 Unified Search]
        QA[💬 Question Answering]
        Viz[📊 Graph Visualization]
    end
    
    J --> KB
    C --> KB
    G --> KB
    
    KB --> Agent
    Agent --> T1
    Agent --> T2
    Agent --> T3
    Agent --> T4
    T2 --> Graph
    T3 --> Graph
    KB --> Graph
    
    Agent --> Search
    Agent --> QA
    Graph --> Viz
```

### How It Works

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend
    participant API as Backend API
    participant Agent as Agentic RAG Agent
    participant Tools as Retrieval Tools
    participant Neo4j as Neo4j
    participant LLM as LLM (Ollama/OpenAI/Azure OpenAI)
    
    User->>UI: Ask question + selected sources
    UI->>API: POST /ask { question, sources }
    API->>Agent: run(messages, documents, allowed_sources)
    Agent->>Tools: Call rag_search_tool / graph_query_tool
    Tools->>Neo4j: Retrieve candidate docs (source-filtered)
    Neo4j-->>Tools: Documents
    Agent->>Tools: Optionally fetch neighbors + filter docs
    Tools-->>Agent: Expanded + filtered context
    Agent->>LLM: Generate grounded answer
    LLM-->>Agent: Answer
    Agent-->>API: Final answer + source docs
    API-->>UI: Response + sources
    UI-->>User: Display answer & links
```

## Configuration

Project Kraken currently supports [ollama](https://ollama.com/), [OpenAI](https://openai.com/api/) and [Azure OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/reference) as your GenAI provider.

Configuration is centralized through:

- `load_env_config()` for environment parsing
- `AppContainer` for dependency wiring and runtime component creation
- provider utility factories for chat generator and embedders

See: [.env.example](../.env.example) and [ARCHITECTURE.md](./ARCHITECTURE.md).

## Chat History & Session Management

Project Kraken implements intelligent chat history management to provide a seamless conversational experience across page reloads and sessions.

### Key Features

**Session Tracking**: 

- Automatic session ID generation and cookie-based persistence
- 30-day session lifetime
- HTTP-only cookies for security

**Conversational Context**:

- Follow-up questions automatically rewritten using chat history
- Last 4 messages used as context for query understanding
- Seamless multi-turn conversations

**History Restoration**:

- Complete chat history restored on page reload
- All messages, responses, and source references preserved
- Instant access to previous conversations
