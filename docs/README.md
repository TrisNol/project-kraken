<img src="./images/project_kraken_landscape.png">

# Release the Kraken

Project Kraken is a **Central Knowledge Base** designed to bring together multiple sources of information
- Git 
- Confluence
- Jira

into a single, unified platform.

With **Project Kraken**, you can:
- 🗂️ Access all your resources in one place
- 🔍 Perform Retrieval-Augmented Generation (RAG) functions for smarter insights
- 🚀 Boost productivity and collaboration across teams

Unleash the power of seamless knowledge integration with Project Kraken! 🦑

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
        RAG[🤖 RAG Engine]
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
    
    KB --> RAG
    KB --> Graph
    
    RAG --> Search
    RAG --> QA
    Graph --> Viz
```

### How It Works

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend
    participant API as Backend API
    participant KB as Knowledge Base
    participant LLM as LLM (Ollama/OpenAI)
    
    User->>UI: Ask Question
    UI->>API: POST /ask
    API->>KB: Retrieve relevant documents
    KB-->>API: Top K documents
    API->>LLM: Generate answer with context
    LLM-->>API: Answer
    API-->>UI: Response + sources
    UI-->>User: Display answer & links
```

## Configuration

You can currently switch between [ollama](https://ollama.com/) and [OpenAI](https://openai.com/api/) as our GenAI provider. This can be configured via a set of environment variables (see: [.env.example](../.env.example)).

