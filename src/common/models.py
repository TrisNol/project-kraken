from pydantic import BaseModel, Field
from typing import List, Union
from enum import Enum

class DocumentSourceType(str, Enum):
    JIRA = "JIRA"
    CONFLUENCE = "CONFLUENCE"
    GITHUB = "GITHUB"

class BaseMetadata(BaseModel):
    source: str = Field(..., description="Source of the document")
    type: DocumentSourceType = Field(..., description="Type of the document source")
    last_updated: str = Field(..., description="Last updated timestamp")

class JiraMetadata(BaseMetadata):
    issue_key: str = Field(..., description="JIRA issue key")
    project_key: str = Field(..., description="JIRA project key")

class ConfluenceMetadata(BaseMetadata):
    page_id: str = Field(..., description="Confluence page ID")
    space_key: str = Field(..., description="Confluence space key")

class GitHubMetadata(BaseMetadata):
    repo_name: str = Field(..., description="GitHub repository name")
    file_path: str = Field(..., description="Path to the file in the repository")
    commit_hash: str = Field(..., description="Commit hash of the file version")
    ref: str = Field(..., description="Branch or tag reference")

class ResponseModel(BaseModel):
    answer: str = Field(..., description="Answer to the question")
    source_documents: List[Union[JiraMetadata, ConfluenceMetadata, GitHubMetadata]] = Field(
        ..., 
        description="List of source documents used to generate the answer, with metadata based on document type"
    )