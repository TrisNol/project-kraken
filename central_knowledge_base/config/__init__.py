"""Configuration management for Central Knowledge Base."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def substitute_env_vars(value: Any) -> Any:
    """Substitute environment variables in config values."""
    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
        env_var = value[2:-1]
        default_value = '' if 'API_KEY' in env_var or 'TOKEN' in env_var else value
        return os.getenv(env_var, default_value)
    return value


class ConnectorConfig(BaseModel):
    """Base configuration for connectors."""
    enabled: bool = True
    

class ConfluenceConfig(ConnectorConfig):
    """Confluence connector configuration."""
    base_url: str = Field(..., description="Confluence base URL")
    username: str = Field(..., description="Confluence username")
    api_token: str = Field(..., description="Confluence API token")
    spaces: list[str] = Field(default_factory=list, description="Space keys to sync")
    
    @field_validator('base_url', 'username', 'api_token', mode='before')
    def substitute_env(cls, v):
        return substitute_env_vars(v)


class JiraConfig(ConnectorConfig):
    """Jira connector configuration."""
    base_url: str = Field(..., description="Jira base URL")
    username: str = Field(..., description="Jira username")
    api_token: str = Field(..., description="Jira API token")
    projects: list[str] = Field(default_factory=list, description="Project keys to sync")
    
    @field_validator('base_url', 'username', 'api_token', mode='before')
    def substitute_env(cls, v):
        return substitute_env_vars(v)


class GitConfig(ConnectorConfig):
    """Git connector configuration."""
    repositories: list[str] = Field(default_factory=list, description="Repository URLs")
    access_token: Optional[str] = Field(None, description="Git access token")
    
    @field_validator('access_token', mode='before')
    def substitute_env(cls, v):
        return substitute_env_vars(v)


class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-3.5-turbo", description="Model name")
    api_key: str = Field(..., description="API key")
    temperature: float = Field(default=0.1, description="Temperature for generation")
    max_tokens: int = Field(default=1000, description="Maximum tokens per response")
    
    @field_validator('api_key', mode='before')
    def substitute_env(cls, v):
        return substitute_env_vars(v)


class VectorStoreConfig(BaseModel):
    """Vector store configuration."""
    provider: str = Field(default="chroma", description="Vector store provider")
    persist_directory: str = Field(default="./data/vectorstore", description="Persistence directory")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model")


class GraphConfig(BaseModel):
    """Knowledge graph configuration."""
    persist_directory: str = Field(default="./data/graph", description="Graph persistence directory")
    similarity_threshold: float = Field(default=0.7, description="Entity similarity threshold")


class APIConfig(BaseModel):
    """API configuration."""
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")


class Config(BaseModel):
    """Main configuration class."""
    confluence: ConfluenceConfig
    jira: JiraConfig
    git: GitConfig
    llm: LLMConfig
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    api: APIConfig = Field(default_factory=APIConfig)


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file."""
    if config_path is None:
        config_path = os.getenv('CKB_CONFIG_PATH', 'config/config.yaml')
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return Config(**config_data)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config