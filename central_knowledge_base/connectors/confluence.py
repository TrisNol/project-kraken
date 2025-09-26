"""Confluence connector for fetching pages and spaces."""

import re
from typing import Iterator, List, Optional
from datetime import datetime
from atlassian import Confluence
from bs4 import BeautifulSoup
import logging

from central_knowledge_base.connectors import BaseConnector, Document, Entity, Relationship
from central_knowledge_base.config import ConfluenceConfig

logger = logging.getLogger(__name__)


class ConfluenceConnector(BaseConnector):
    """Connector for Atlassian Confluence."""
    
    def __init__(self, config: ConfluenceConfig):
        super().__init__(config)
        self.client = Confluence(
            url=config.base_url,
            username=config.username,
            password=config.api_token,
            cloud=True
        )
    
    def test_connection(self) -> bool:
        """Test Confluence connection."""
        try:
            self.client.get_all_spaces(limit=1)
            return True
        except Exception as e:
            self.logger.error(f"Confluence connection test failed: {e}")
            return False
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "confluence"
    
    def fetch_documents(self, spaces: Optional[List[str]] = None, **kwargs) -> Iterator[Document]:
        """Fetch pages from Confluence spaces."""
        target_spaces = spaces or self.config.spaces
        
        for space_key in target_spaces:
            self.logger.info(f"Fetching pages from Confluence space: {space_key}")
            
            try:
                # Get all pages in the space
                pages = self.client.get_all_pages_from_space(
                    space=space_key,
                    start=0,
                    limit=500,
                    expand="body.storage,version,history"
                )
                
                for page in pages:
                    yield self._convert_page_to_document(page, space_key)
                    
            except Exception as e:
                self.logger.error(f"Error fetching pages from space {space_key}: {e}")
                continue
    
    def _convert_page_to_document(self, page: dict, space_key: str) -> Document:
        """Convert Confluence page to Document."""
        page_id = page['id']
        title = page['title']
        
        # Extract content from storage format
        content_html = page.get('body', {}).get('storage', {}).get('value', '')
        content = self._html_to_text(content_html)
        
        # Extract metadata
        version = page.get('version', {})
        history = page.get('history', {})
        
        # Get creation and modification dates
        created_at = None
        updated_at = None
        author = None
        
        if version:
            updated_at = self._parse_confluence_date(version.get('when'))
            if 'by' in version and 'displayName' in version['by']:
                author = version['by']['displayName']
        
        if history and 'createdDate' in history:
            created_at = self._parse_confluence_date(history['createdDate'])
        
        # Build page URL
        url = f"{self.config.base_url}/wiki/spaces/{space_key}/pages/{page_id}"
        
        metadata = {
            'space_key': space_key,
            'page_id': page_id,
            'version': version.get('number'),
            'labels': [label['name'] for label in page.get('metadata', {}).get('labels', {}).get('results', [])],
            'content_length': len(content)
        }
        
        return Document(
            id=f"confluence_{space_key}_{page_id}",
            title=title,
            content=content,
            source=f"confluence_space_{space_key}",
            source_type="confluence",
            url=url,
            created_at=created_at,
            updated_at=updated_at,
            author=author,
            metadata=metadata
        )
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _parse_confluence_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Confluence date string to datetime."""
        if not date_str:
            return None
        
        try:
            # Remove timezone info and microseconds for parsing
            clean_date = re.sub(r'\.\d{3}[+-]\d{4}$', '', date_str)
            return datetime.fromisoformat(clean_date.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse date: {date_str}")
            return None
    
    def extract_entities(self, documents: List[Document]) -> List[Entity]:
        """Extract Confluence-specific entities."""
        entities = super().extract_entities(documents)
        
        # Extract space entities
        spaces = set()
        for doc in documents:
            space_key = doc.metadata.get('space_key')
            if space_key:
                spaces.add(space_key)
        
        for space_key in spaces:
            space_docs = [doc.id for doc in documents if doc.metadata.get('space_key') == space_key]
            entities.append(Entity(
                name=f"Confluence Space: {space_key}",
                type="confluence_space",
                description=f"Confluence space containing {len(space_docs)} documents",
                source_documents=space_docs,
                metadata={'space_key': space_key}
            ))
        
        # Extract mentioned users from content (basic implementation)
        user_mentions = set()
        for doc in documents:
            # Look for @mentions in content
            mentions = re.findall(r'@(\w+)', doc.content)
            user_mentions.update(mentions)
        
        for user in user_mentions:
            user_docs = [doc.id for doc in documents if f'@{user}' in doc.content]
            entities.append(Entity(
                name=user,
                type="person",
                description=f"User mentioned in {len(user_docs)} documents",
                source_documents=user_docs
            ))
        
        return entities
    
    def extract_relationships(self, entities: List[Entity], documents: List[Document]) -> List[Relationship]:
        """Extract Confluence-specific relationships."""
        relationships = super().extract_relationships(entities, documents)
        
        # Create relationships between documents and spaces
        entity_map = {e.name: e for e in entities}
        
        for doc in documents:
            space_key = doc.metadata.get('space_key')
            if space_key:
                space_entity_name = f"Confluence Space: {space_key}"
                doc_entity_name = doc.title
                
                if space_entity_name in entity_map and doc_entity_name in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc_entity_name,
                        target_entity=space_entity_name,
                        relationship_type="belongs_to",
                        source_documents=[doc.id]
                    ))
        
        return relationships