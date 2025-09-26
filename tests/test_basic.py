"""Basic tests for Central Knowledge Base."""

import pytest
from unittest.mock import Mock, patch
from central_knowledge_base.connectors import Document, Entity, Relationship
from central_knowledge_base.config import Config, LLMConfig, VectorStoreConfig, GraphConfig, APIConfig
from central_knowledge_base.config import ConfluenceConfig, JiraConfig, GitConfig


def test_document_creation():
    """Test Document model creation."""
    doc = Document(
        id="test_doc_1",
        title="Test Document",
        content="This is test content.",
        source="test_source",
        source_type="test",
        author="Test Author"
    )
    
    assert doc.id == "test_doc_1"
    assert doc.title == "Test Document"
    assert doc.source_type == "test"
    assert doc.author == "Test Author"


def test_entity_creation():
    """Test Entity model creation."""
    entity = Entity(
        name="Test Entity",
        type="test_type",
        description="A test entity",
        source_documents=["doc_1", "doc_2"]
    )
    
    assert entity.name == "Test Entity"
    assert entity.type == "test_type"
    assert len(entity.source_documents) == 2


def test_relationship_creation():
    """Test Relationship model creation."""
    rel = Relationship(
        source_entity="Entity A",
        target_entity="Entity B",
        relationship_type="related_to",
        confidence=0.8
    )
    
    assert rel.source_entity == "Entity A"
    assert rel.target_entity == "Entity B"
    assert rel.relationship_type == "related_to"
    assert rel.confidence == 0.8


def test_config_creation():
    """Test configuration creation."""
    config = Config(
        confluence=ConfluenceConfig(
            base_url="https://test.atlassian.net",
            username="test@example.com",
            api_token="test_token"
        ),
        jira=JiraConfig(
            base_url="https://test.atlassian.net",
            username="test@example.com", 
            api_token="test_token"
        ),
        git=GitConfig(
            repositories=["https://github.com/test/repo"]
        ),
        llm=LLMConfig(
            api_key="test_key"
        )
    )
    
    assert config.confluence.base_url == "https://test.atlassian.net"
    assert config.jira.username == "test@example.com"
    assert len(config.git.repositories) == 1
    assert config.llm.model == "gpt-3.5-turbo"  # default value


@patch('central_knowledge_base.connectors.confluence.Confluence')
def test_confluence_connector_initialization(mock_confluence):
    """Test Confluence connector initialization."""
    from central_knowledge_base.connectors.confluence import ConfluenceConnector
    
    config = ConfluenceConfig(
        base_url="https://test.atlassian.net",
        username="test@example.com",
        api_token="test_token"
    )
    
    connector = ConfluenceConnector(config)
    assert connector.get_source_type() == "confluence"
    
    # Verify Confluence client was initialized with correct parameters
    mock_confluence.assert_called_once_with(
        url="https://test.atlassian.net",
        username="test@example.com", 
        password="test_token",
        cloud=True
    )


@patch('central_knowledge_base.connectors.jira.Jira')
def test_jira_connector_initialization(mock_jira):
    """Test Jira connector initialization."""
    from central_knowledge_base.connectors.jira import JiraConnector
    
    config = JiraConfig(
        base_url="https://test.atlassian.net",
        username="test@example.com",
        api_token="test_token"
    )
    
    connector = JiraConnector(config)
    assert connector.get_source_type() == "jira"
    
    # Verify Jira client was initialized with correct parameters
    mock_jira.assert_called_once_with(
        url="https://test.atlassian.net",
        username="test@example.com",
        password="test_token", 
        cloud=True
    )


def test_git_connector_initialization():
    """Test Git connector initialization."""
    from central_knowledge_base.connectors.git import GitConnector
    
    config = GitConfig(
        repositories=["https://github.com/test/repo1", "https://github.com/test/repo2"]
    )
    
    connector = GitConnector(config)
    assert connector.get_source_type() == "git"
    assert len(connector.config.repositories) == 2


if __name__ == "__main__":
    pytest.main([__file__])