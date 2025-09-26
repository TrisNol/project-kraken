#!/usr/bin/env python3
"""
Demo script for Central Knowledge Base

This script demonstrates the core functionality of the RAG application
including data ingestion, knowledge graph creation, and querying.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from central_knowledge_base.config import Config, ConfluenceConfig, JiraConfig, GitConfig, LLMConfig, VectorStoreConfig, GraphConfig
from central_knowledge_base.connectors import Document, Entity, Relationship
from central_knowledge_base.graph import KnowledgeGraph


def create_demo_data():
    """Create some demo documents, entities, and relationships."""
    print("📚 Creating demo data...")
    
    # Create sample documents
    documents = [
        Document(
            id="doc_1",
            title="Project Alpha Overview",
            content="""Project Alpha is a web application built using React and Node.js. 
            The project is led by John Doe and includes features for user authentication, 
            data visualization, and real-time notifications. The backend uses PostgreSQL 
            for data storage and Redis for caching. The team includes Sarah Smith (frontend), 
            Mike Johnson (backend), and Lisa Wong (DevOps).""",
            source="confluence_space_PROJ",
            source_type="confluence",
            author="John Doe",
            metadata={"space_key": "PROJ", "labels": ["project", "web-app"]}
        ),
        Document(
            id="doc_2", 
            title="[PROJ-123] Authentication System Bug",
            content="""Bug in the authentication system where users are unable to login 
            after password reset. The issue affects the /auth/login endpoint and appears 
            to be related to session management. Assigned to Mike Johnson for investigation. 
            Priority: High. Component: Authentication. Status: In Progress.""",
            source="jira_project_PROJ",
            source_type="jira",
            author="Sarah Smith",
            metadata={"project_key": "PROJ", "issue_key": "PROJ-123", "status": "In Progress", "assignee": "Mike Johnson"}
        ),
        Document(
            id="doc_3",
            title="project-alpha: src/auth/login.js", 
            content="""const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const User = require('../models/User');

// Login endpoint
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
    
    if (!user || !await bcrypt.compare(password, user.password)) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET);
    res.json({ token, user: { id: user._id, email: user.email } });
  } catch (error) {
    res.status(500).json({ error: 'Login failed' });
  }
});""",
            source="git_repo_project-alpha",
            source_type="git",
            author="Mike Johnson", 
            metadata={"repo_name": "project-alpha", "file_path": "src/auth/login.js", "file_extension": ".js"}
        ),
        Document(
            id="doc_4",
            title="Team Meeting Notes - Sprint Planning",
            content="""Sprint planning meeting for Project Alpha. Discussed upcoming features
            and bug fixes. John Doe presented the roadmap. Sarah Smith reported frontend 
            progress. Mike Johnson identified authentication issues that need immediate attention.
            Lisa Wong outlined deployment pipeline improvements. Next meeting scheduled for
            next Friday. Action items: Fix PROJ-123 (Mike), Update documentation (Sarah),
            Setup monitoring (Lisa).""",
            source="confluence_space_TEAM", 
            source_type="confluence",
            author="John Doe",
            metadata={"space_key": "TEAM", "meeting_date": "2024-01-15"}
        )
    ]
    
    # Create sample entities  
    entities = [
        Entity(name="John Doe", type="person", description="Project lead for Project Alpha", source_documents=["doc_1", "doc_4"]),
        Entity(name="Sarah Smith", type="person", description="Frontend developer", source_documents=["doc_1", "doc_2", "doc_4"]),
        Entity(name="Mike Johnson", type="person", description="Backend developer", source_documents=["doc_1", "doc_2", "doc_3", "doc_4"]),
        Entity(name="Lisa Wong", type="person", description="DevOps engineer", source_documents=["doc_1", "doc_4"]),
        Entity(name="Project Alpha", type="project", description="Web application project", source_documents=["doc_1", "doc_2", "doc_3", "doc_4"]),
        Entity(name="Authentication System", type="component", description="User login and session management", source_documents=["doc_1", "doc_2", "doc_3"]),
        Entity(name="React", type="technology", description="Frontend JavaScript framework", source_documents=["doc_1"]),
        Entity(name="Node.js", type="technology", description="Backend JavaScript runtime", source_documents=["doc_1"]),
        Entity(name="PostgreSQL", type="technology", description="Relational database", source_documents=["doc_1"]),
    ]
    
    # Create sample relationships
    relationships = [
        Relationship("John Doe", "Project Alpha", "leads", 1.0, ["doc_1"]),
        Relationship("Sarah Smith", "Project Alpha", "works_on", 1.0, ["doc_1"]), 
        Relationship("Mike Johnson", "Project Alpha", "works_on", 1.0, ["doc_1"]),
        Relationship("Lisa Wong", "Project Alpha", "works_on", 1.0, ["doc_1"]),
        Relationship("Mike Johnson", "[PROJ-123] Authentication System Bug", "assigned_to", 1.0, ["doc_2"]),
        Relationship("Authentication System", "Project Alpha", "component_of", 1.0, ["doc_1"]),
        Relationship("React", "Project Alpha", "used_in", 1.0, ["doc_1"]),
        Relationship("Node.js", "Project Alpha", "used_in", 1.0, ["doc_1"]),
        Relationship("PostgreSQL", "Project Alpha", "used_in", 1.0, ["doc_1"]),
        Relationship("Mike Johnson", "src/auth/login.js", "authored", 1.0, ["doc_3"]),
        Relationship("Authentication System", "[PROJ-123] Authentication System Bug", "has_bug", 0.9, ["doc_2"]),
    ]
    
    return documents, entities, relationships


def demo_knowledge_graph():
    """Demonstrate knowledge graph functionality."""
    print("\n🕸️  Demonstrating Knowledge Graph...")
    
    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    print(f"   Using temporary directory: {temp_dir}")
    
    try:
        # Create graph config
        graph_config = GraphConfig(persist_directory=temp_dir)
        kg = KnowledgeGraph(graph_config)
        
        # Get demo data
        documents, entities, relationships = create_demo_data()
        
        # Add data to knowledge graph
        kg.add_documents(documents)
        kg.add_entities(entities) 
        kg.add_relationships(relationships)
        
        # Print statistics
        stats = kg.get_statistics()
        print(f"   📊 Knowledge Graph Statistics:")
        print(f"      • Documents: {stats['total_documents']}")
        print(f"      • Entities: {stats['total_entities']}")
        print(f"      • Relationships: {stats['total_relationships']}")
        
        print(f"\n   🏷️  Entity Types:")
        for entity_type, count in stats['entity_types'].items():
            print(f"      • {entity_type}: {count}")
        
        print(f"\n   🔗 Relationship Types:")
        for rel_type, count in stats['relationship_types'].items():
            print(f"      • {rel_type}: {count}")
        
        # Demonstrate entity neighbors
        print(f"\n   🌐 Entity Relationships (Mike Johnson):")
        neighbors = kg.get_entity_neighbors("Mike Johnson", max_depth=2)
        for entity_name, data in neighbors.items():
            if data['depth'] == 0:  # Direct neighbors only
                print(f"      • {entity_name}:")
                for neighbor in data['neighbors']:
                    direction = "→" if neighbor['direction'] == 'outgoing' else "←"
                    print(f"        {direction} {neighbor['relationship']} → {neighbor['entity']}")
        
        # Demonstrate path finding
        print(f"\n   🛤️  Paths from 'John Doe' to 'Authentication System':")
        paths = kg.find_path("John Doe", "Authentication System", max_length=3)
        for i, path in enumerate(paths[:3], 1):  # Show first 3 paths
            print(f"      Path {i}: {' → '.join(path)}")
        
        # Save and reload demonstration
        kg.save("demo_graph.pkl")
        print(f"\n   💾 Knowledge graph saved successfully")
        
        # Create new instance and load
        kg2 = KnowledgeGraph(graph_config)
        if kg2.load("demo_graph.pkl"):
            print(f"   📂 Knowledge graph loaded successfully")
            stats2 = kg2.get_statistics()
            print(f"      Loaded {stats2['total_entities']} entities and {stats2['total_relationships']} relationships")
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


def demo_connector_framework():
    """Demonstrate the connector framework."""
    print("\n🔌 Demonstrating Connector Framework...")
    
    from central_knowledge_base.connectors import BaseConnector, ConnectorResult
    
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
    
    # Show some extracted entities
    print(f"\n   🏷️  Extracted Entities (first 5):")
    for entity in result.entities[:5]:
        print(f"      • {entity.name} ({entity.type})")


def demo_config_system():
    """Demonstrate configuration system."""
    print("\n⚙️  Demonstrating Configuration System...")
    
    # Set environment variables for demo
    os.environ.update({
        'DEMO_API_KEY': 'demo-secret-key-123',
        'DEMO_BASE_URL': 'https://demo.example.com',
        'DEMO_USERNAME': 'demo-user@example.com'
    })
    
    # Create demo config with env var substitution
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
            'repositories': ['https://github.com/demo/repo'],
            'access_token': '${DEMO_API_KEY}'
        },
        'llm': {
            'provider': 'openai',
            'model': 'gpt-3.5-turbo',
            'api_key': '${DEMO_API_KEY}',
            'temperature': 0.1
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
        print(f"   🌡️  Temperature: {config.llm.temperature}")
        
    except Exception as e:
        print(f"   ❌ Configuration failed: {e}")


def main():
    """Run the demo."""
    print("🚀 Central Knowledge Base Demo")
    print("=" * 50)
    
    print("\n📖 This demo showcases the core functionality of the RAG application:")
    print("   • Document and entity modeling")  
    print("   • Knowledge graph construction")
    print("   • Connector framework")
    print("   • Configuration management")
    
    try:
        demo_config_system()
        demo_connector_framework()  
        demo_knowledge_graph()
        
        print("\n🎉 Demo completed successfully!")
        print("\n📚 Next steps:")
        print("   1. Install additional dependencies: pip install langchain langgraph chromadb")
        print("   2. Set up your configuration in config/config.yaml")
        print("   3. Configure API keys in .env file")
        print("   4. Run: ckb sync --sources confluence jira git")
        print("   5. Start API server: ckb run")
        print("   6. Query your knowledge base: ckb query 'What is Project Alpha?'")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()