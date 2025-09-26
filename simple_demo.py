#!/usr/bin/env python3
"""
Simple demo script for Central Knowledge Base

This script demonstrates the core functionality without heavy dependencies.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from central_knowledge_base.config import Config, ConfluenceConfig, JiraConfig, GitConfig, LLMConfig
from central_knowledge_base.connectors import Document, Entity, Relationship


def create_demo_data():
    """Create some demo documents, entities, and relationships."""
    print("📚 Creating demo data...")
    
    documents = [
        Document(
            id="doc_1",
            title="Project Alpha Overview", 
            content="""Project Alpha is a web application built using React and Node.js. 
            The project is led by John Doe and includes features for user authentication, 
            data visualization, and real-time notifications.""",
            source="confluence_space_PROJ",
            source_type="confluence",
            author="John Doe",
            metadata={"space_key": "PROJ"}
        ),
        Document(
            id="doc_2",
            title="[PROJ-123] Authentication Bug",
            content="""Bug in authentication system. Assigned to Mike Johnson. Priority: High.""",
            source="jira_project_PROJ", 
            source_type="jira",
            author="Sarah Smith",
            metadata={"project_key": "PROJ", "assignee": "Mike Johnson"}
        ),
        Document(
            id="doc_3", 
            title="project-alpha: login.js",
            content="""const login = async (req, res) => {
  // Login implementation
  const user = await User.findOne({ email });
  // ... authentication logic
};""",
            source="git_repo_project-alpha",
            source_type="git", 
            author="Mike Johnson",
            metadata={"repo_name": "project-alpha", "file_extension": ".js"}
        )
    ]
    
    entities = [
        Entity(name="John Doe", type="person", description="Project lead", source_documents=["doc_1"]),
        Entity(name="Mike Johnson", type="person", description="Backend developer", source_documents=["doc_2", "doc_3"]),
        Entity(name="Project Alpha", type="project", description="Web application", source_documents=["doc_1", "doc_2", "doc_3"]),
        Entity(name="Authentication System", type="component", description="User login system", source_documents=["doc_2", "doc_3"])
    ]
    
    relationships = [
        Relationship(
            source_entity="John Doe", 
            target_entity="Project Alpha", 
            relationship_type="leads", 
            confidence=1.0, 
            source_documents=["doc_1"]
        ),
        Relationship(
            source_entity="Mike Johnson", 
            target_entity="[PROJ-123] Authentication Bug", 
            relationship_type="assigned_to", 
            confidence=1.0, 
            source_documents=["doc_2"]
        ),
        Relationship(
            source_entity="Authentication System", 
            target_entity="Project Alpha", 
            relationship_type="component_of", 
            confidence=1.0, 
            source_documents=["doc_1"]
        )
    ]
    
    return documents, entities, relationships


def demo_basic_models():
    """Demonstrate basic data models."""
    print("\n📄 Demonstrating Basic Models...")
    
    documents, entities, relationships = create_demo_data()
    
    print(f"   📊 Created {len(documents)} documents, {len(entities)} entities, {len(relationships)} relationships")
    
    print("\n   📋 Sample Document:")
    doc = documents[0]
    print(f"      • ID: {doc.id}")
    print(f"      • Title: {doc.title}")
    print(f"      • Source: {doc.source_type}")
    print(f"      • Author: {doc.author}")
    print(f"      • Content: {doc.content[:100]}...")
    
    print("\n   🏷️  Sample Entity:")
    entity = entities[0]
    print(f"      • Name: {entity.name}")
    print(f"      • Type: {entity.type}")
    print(f"      • Description: {entity.description}")
    print(f"      • Documents: {len(entity.source_documents)}")
    
    print("\n   🔗 Sample Relationship:")
    rel = relationships[0]
    print(f"      • {rel.source_entity} --{rel.relationship_type}--> {rel.target_entity}")
    print(f"      • Confidence: {rel.confidence}")


def demo_connector_framework():
    """Demonstrate the connector framework."""
    print("\n🔌 Demonstrating Connector Framework...")
    
    from central_knowledge_base.connectors import BaseConnector
    
    class DemoConnector(BaseConnector):
        """Demo connector for testing."""
        
        def __init__(self, config=None):
            super().__init__(config or {})
        
        def test_connection(self):
            return True
        
        def fetch_documents(self, **kwargs):
            """Return demo documents."""
            documents, _, _ = create_demo_data()
            for doc in documents:
                yield doc
        
        def get_source_type(self):
            return "demo"
    
    # Test the connector
    connector = DemoConnector()
    print(f"   📡 Connector type: {connector.get_source_type()}")
    print(f"   ✅ Connection test: {'PASS' if connector.test_connection() else 'FAIL'}")
    
    # Sync data
    result = connector.sync()
    print(f"   📋 Sync results:")
    print(f"      • Documents: {len(result.documents)}")
    print(f"      • Entities: {len(result.entities)}")
    print(f"      • Relationships: {len(result.relationships)}")
    
    # Show document titles
    print(f"\n   📄 Document Titles:")
    for doc in result.documents:
        print(f"      • {doc.title}")


def demo_config_system():
    """Demonstrate configuration system.""" 
    print("\n⚙️  Demonstrating Configuration System...")
    
    # Set environment variables for demo
    os.environ.update({
        'DEMO_API_KEY': 'demo-secret-key-123',
        'DEMO_BASE_URL': 'https://demo.example.com',
        'DEMO_USERNAME': 'demo-user@example.com'
    })
    
    demo_config_data = {
        'confluence': {
            'enabled': True,
            'base_url': '${DEMO_BASE_URL}',
            'username': '${DEMO_USERNAME}',
            'api_token': '${DEMO_API_KEY}',
            'spaces': ['DEMO', 'TEST']
        },
        'jira': {
            'enabled': True, 
            'base_url': '${DEMO_BASE_URL}',
            'username': '${DEMO_USERNAME}',
            'api_token': '${DEMO_API_KEY}',
            'projects': ['DEMO']
        },
        'git': {
            'enabled': True,
            'repositories': ['https://github.com/demo/repo']
        },
        'llm': {
            'provider': 'openai',
            'model': 'gpt-3.5-turbo', 
            'api_key': '${DEMO_API_KEY}'
        }
    }
    
    try:
        config = Config(**demo_config_data)
        print(f"   ✅ Configuration loaded successfully")
        print(f"   🔑 API key (masked): {config.llm.api_key[:8]}***")
        print(f"   🌐 Base URL: {config.confluence.base_url}")
        print(f"   👤 Username: {config.confluence.username}")
        print(f"   📂 Confluence spaces: {config.confluence.spaces}")
        print(f"   🔧 LLM model: {config.llm.model}")
        
    except Exception as e:
        print(f"   ❌ Configuration failed: {e}")


def demo_cli_interface():
    """Demonstrate CLI interface design."""
    print("\n💻 CLI Interface Design...")
    
    print("   Available commands:")
    print("   • ckb run                    - Start API server")
    print("   • ckb sync --sources all     - Sync data from all sources")
    print("   • ckb query 'your question'  - Query the knowledge base")  
    print("   • ckb stats                  - Show system statistics")
    print("   • ckb test                   - Test connector connections")
    
    print("\n   Example usage:")
    print("   $ ckb sync --sources confluence jira")
    print("   $ ckb query 'What is Project Alpha?'")
    print("   $ ckb run --host 0.0.0.0 --port 8000")


def demo_api_endpoints():
    """Demonstrate API endpoint design."""
    print("\n🌐 API Endpoints Design...")
    
    endpoints = [
        ("GET", "/", "API information"),
        ("GET", "/health", "Health check and component status"),
        ("GET", "/stats", "System statistics"),
        ("POST", "/api/v1/query", "Query the knowledge base"),
        ("POST", "/api/v1/ingest", "Ingest data from sources"),
        ("GET", "/api/v1/entities", "List entities"),
        ("GET", "/api/v1/entities/{name}", "Get entity details"),
    ]
    
    print("   Available endpoints:")
    for method, path, desc in endpoints:
        print(f"   • {method:<6} {path:<25} - {desc}")
    
    print("\n   Example API calls:")
    print("   POST /api/v1/query")
    print("   {\"question\": \"What bugs are assigned to Mike Johnson?\"}")
    print("")
    print("   POST /api/v1/ingest") 
    print("   {\"source\": \"confluence\", \"parameters\": {\"spaces\": [\"PROJ\"]}}")


def main():
    """Run the simple demo."""
    print("🚀 Central Knowledge Base - Simple Demo")
    print("=" * 50)
    
    print("\n📖 This demo showcases the core architecture and functionality:")
    print("   • Pydantic data models for Documents, Entities, Relationships")
    print("   • Configuration system with environment variable substitution")
    print("   • Connector framework for external data sources")
    print("   • CLI and API interface design")
    
    try:
        demo_config_system()
        demo_basic_models()
        demo_connector_framework()
        demo_cli_interface()
        demo_api_endpoints()
        
        print("\n🎉 Simple demo completed successfully!")
        print("\n📚 Architecture Overview:")
        print("   ┌─ connectors/          (Confluence, Jira, Git)")
        print("   ├─ graph/              (Knowledge graph with NetworkX)")  
        print("   ├─ rag/                (RAG pipeline with LangGraph)")
        print("   ├─ api/                (FastAPI server)")
        print("   ├─ config/             (Configuration management)")
        print("   └─ cli.py              (Command-line interface)")
        
        print("\n🔧 Next steps:")
        print("   1. Install full dependencies (see pyproject.toml)")
        print("   2. Configure your data sources in config/config.yaml")
        print("   3. Set API keys in .env file") 
        print("   4. Run: python -m central_knowledge_base.cli sync")
        print("   5. Start server: python -m central_knowledge_base.cli run")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()