"""Jira connector for fetching issues and projects."""

import re
from typing import Iterator, List, Optional
from datetime import datetime
from atlassian import Jira
import logging

from central_knowledge_base.connectors import BaseConnector, Document, Entity, Relationship
from central_knowledge_base.config import JiraConfig

logger = logging.getLogger(__name__)


class JiraConnector(BaseConnector):
    """Connector for Atlassian Jira."""
    
    def __init__(self, config: JiraConfig):
        super().__init__(config)
        self.client = Jira(
            url=config.base_url,
            username=config.username,
            password=config.api_token,
            cloud=True
        )
    
    def test_connection(self) -> bool:
        """Test Jira connection."""
        try:
            self.client.myself()
            return True
        except Exception as e:
            self.logger.error(f"Jira connection test failed: {e}")
            return False
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "jira"
    
    def fetch_documents(self, projects: Optional[List[str]] = None, **kwargs) -> Iterator[Document]:
        """Fetch issues from Jira projects."""
        target_projects = projects or self.config.projects
        
        for project_key in target_projects:
            self.logger.info(f"Fetching issues from Jira project: {project_key}")
            
            try:
                # Use JQL to get all issues in the project
                jql = f"project = {project_key}"
                issues = self.client.jql(
                    jql,
                    limit=1000,
                    fields="summary,description,status,assignee,reporter,created,updated,issuetype,priority,components,labels,comments"
                )
                
                for issue in issues.get('issues', []):
                    yield self._convert_issue_to_document(issue, project_key)
                    
            except Exception as e:
                self.logger.error(f"Error fetching issues from project {project_key}: {e}")
                continue
    
    def _convert_issue_to_document(self, issue: dict, project_key: str) -> Document:
        """Convert Jira issue to Document."""
        issue_key = issue['key']
        fields = issue['fields']
        
        title = f"[{issue_key}] {fields.get('summary', '')}"
        
        # Build content from description and comments
        content_parts = []
        
        description = fields.get('description', '')
        if description:
            content_parts.append(f"Description: {description}")
        
        # Add issue details
        status = fields.get('status', {}).get('name', 'Unknown')
        issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
        priority = fields.get('priority', {}).get('name', 'Unknown')
        
        content_parts.append(f"Status: {status}")
        content_parts.append(f"Type: {issue_type}")
        content_parts.append(f"Priority: {priority}")
        
        # Add assignee and reporter
        assignee = fields.get('assignee', {})
        if assignee:
            assignee_name = assignee.get('displayName', assignee.get('name', ''))
            content_parts.append(f"Assignee: {assignee_name}")
        
        reporter = fields.get('reporter', {})
        reporter_name = ""
        if reporter:
            reporter_name = reporter.get('displayName', reporter.get('name', ''))
            content_parts.append(f"Reporter: {reporter_name}")
        
        # Add components and labels
        components = [comp.get('name', '') for comp in fields.get('components', [])]
        if components:
            content_parts.append(f"Components: {', '.join(components)}")
        
        labels = fields.get('labels', [])
        if labels:
            content_parts.append(f"Labels: {', '.join(labels)}")
        
        # Add comments
        comments = fields.get('comment', {}).get('comments', [])
        if comments:
            content_parts.append("Comments:")
            for comment in comments[:10]:  # Limit to first 10 comments
                author = comment.get('author', {}).get('displayName', 'Unknown')
                body = comment.get('body', '')
                content_parts.append(f"- {author}: {body}")
        
        content = '\n'.join(content_parts)
        
        # Parse dates
        created_at = self._parse_jira_date(fields.get('created'))
        updated_at = self._parse_jira_date(fields.get('updated'))
        
        # Build issue URL
        url = f"{self.config.base_url}/browse/{issue_key}"
        
        metadata = {
            'project_key': project_key,
            'issue_key': issue_key,
            'issue_type': issue_type,
            'status': status,
            'priority': priority,
            'assignee': assignee.get('displayName') if assignee else None,
            'reporter': reporter.get('displayName') if reporter else None,
            'components': components,
            'labels': labels,
            'comment_count': len(comments)
        }
        
        return Document(
            id=f"jira_{project_key}_{issue_key}",
            title=title,
            content=content,
            source=f"jira_project_{project_key}",
            source_type="jira",
            url=url,
            created_at=created_at,
            updated_at=updated_at,
            author=reporter_name,
            metadata=metadata
        )
    
    def _parse_jira_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Jira date string to datetime."""
        if not date_str:
            return None
        
        try:
            # Jira dates are in ISO format with timezone
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse date: {date_str}")
            return None
    
    def extract_entities(self, documents: List[Document]) -> List[Entity]:
        """Extract Jira-specific entities."""
        entities = super().extract_entities(documents)
        
        # Extract project entities
        projects = set()
        components = set()
        assignees = set()
        reporters = set()
        
        for doc in documents:
            metadata = doc.metadata
            
            # Project entities
            project_key = metadata.get('project_key')
            if project_key:
                projects.add(project_key)
            
            # Component entities
            doc_components = metadata.get('components', [])
            components.update(doc_components)
            
            # People entities
            assignee = metadata.get('assignee')
            if assignee:
                assignees.add(assignee)
            
            reporter = metadata.get('reporter')
            if reporter:
                reporters.add(reporter)
        
        # Add project entities
        for project_key in projects:
            project_docs = [doc.id for doc in documents if doc.metadata.get('project_key') == project_key]
            entities.append(Entity(
                name=f"Jira Project: {project_key}",
                type="jira_project",
                description=f"Jira project containing {len(project_docs)} issues",
                source_documents=project_docs,
                metadata={'project_key': project_key}
            ))
        
        # Add component entities
        for component in components:
            component_docs = [doc.id for doc in documents if component in doc.metadata.get('components', [])]
            entities.append(Entity(
                name=f"Component: {component}",
                type="component",
                description=f"Component mentioned in {len(component_docs)} issues",
                source_documents=component_docs
            ))
        
        # Add people entities (assignees and reporters)
        all_people = assignees.union(reporters)
        for person in all_people:
            person_docs = []
            for doc in documents:
                if (doc.metadata.get('assignee') == person or 
                    doc.metadata.get('reporter') == person):
                    person_docs.append(doc.id)
            
            entities.append(Entity(
                name=person,
                type="person",
                description=f"Person involved in {len(person_docs)} issues",
                source_documents=person_docs
            ))
        
        return entities
    
    def extract_relationships(self, entities: List[Entity], documents: List[Document]) -> List[Relationship]:
        """Extract Jira-specific relationships."""
        relationships = super().extract_relationships(entities, documents)
        
        entity_map = {e.name: e for e in entities}
        
        for doc in documents:
            metadata = doc.metadata
            
            # Issue -> Project relationships
            project_key = metadata.get('project_key')
            if project_key:
                project_entity_name = f"Jira Project: {project_key}"
                if project_entity_name in entity_map and doc.title in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc.title,
                        target_entity=project_entity_name,
                        relationship_type="belongs_to",
                        source_documents=[doc.id]
                    ))
            
            # Issue -> Component relationships
            components = metadata.get('components', [])
            for component in components:
                component_entity_name = f"Component: {component}"
                if component_entity_name in entity_map and doc.title in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc.title,
                        target_entity=component_entity_name,
                        relationship_type="uses_component",
                        source_documents=[doc.id]
                    ))
            
            # Person -> Issue relationships
            assignee = metadata.get('assignee')
            if assignee and assignee in entity_map and doc.title in entity_map:
                relationships.append(Relationship(
                    source_entity=assignee,
                    target_entity=doc.title,
                    relationship_type="assigned_to",
                    source_documents=[doc.id]
                ))
            
            reporter = metadata.get('reporter')
            if reporter and reporter in entity_map and doc.title in entity_map:
                relationships.append(Relationship(
                    source_entity=reporter,
                    target_entity=doc.title,
                    relationship_type="reported",
                    source_documents=[doc.id]
                ))
        
        return relationships