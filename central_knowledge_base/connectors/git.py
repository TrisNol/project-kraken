"""Git connector for fetching repository content and history."""

import os
import tempfile
from typing import Iterator, List, Optional
from datetime import datetime
from pathlib import Path
import git
import logging

from central_knowledge_base.connectors import BaseConnector, Document, Entity, Relationship
from central_knowledge_base.config import GitConfig

logger = logging.getLogger(__name__)


class GitConnector(BaseConnector):
    """Connector for Git repositories."""
    
    def __init__(self, config: GitConfig):
        super().__init__(config)
        self.temp_dirs = []
    
    def __del__(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    
    def test_connection(self) -> bool:
        """Test Git connectivity by trying to clone the first repository."""
        if not self.config.repositories:
            return False
        
        try:
            repo_url = self.config.repositories[0]
            temp_dir = tempfile.mkdtemp()
            self.temp_dirs.append(temp_dir)
            
            # Try to clone a shallow copy
            git.Repo.clone_from(repo_url, temp_dir, depth=1)
            return True
        except Exception as e:
            self.logger.error(f"Git connection test failed: {e}")
            return False
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "git"
    
    def fetch_documents(self, repositories: Optional[List[str]] = None, **kwargs) -> Iterator[Document]:
        """Fetch documents from Git repositories."""
        target_repos = repositories or self.config.repositories
        max_files_per_repo = kwargs.get('max_files', 1000)
        
        for repo_url in target_repos:
            self.logger.info(f"Fetching content from Git repository: {repo_url}")
            
            try:
                # Clone repository to temporary directory
                temp_dir = tempfile.mkdtemp()
                self.temp_dirs.append(temp_dir)
                
                repo = git.Repo.clone_from(repo_url, temp_dir)
                repo_name = self._extract_repo_name(repo_url)
                
                # Get repository files
                file_count = 0
                for file_doc in self._process_repository_files(repo, repo_name, temp_dir):
                    if file_count >= max_files_per_repo:
                        break
                    yield file_doc
                    file_count += 1
                
                # Get commit history documents (limited)
                commit_count = 0
                max_commits = kwargs.get('max_commits', 100)
                for commit_doc in self._process_commit_history(repo, repo_name, max_commits):
                    if commit_count >= max_commits:
                        break
                    yield commit_doc
                    commit_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing repository {repo_url}: {e}")
                continue
    
    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL."""
        # Handle both HTTPS and SSH URLs
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        return repo_url.split('/')[-1]
    
    def _process_repository_files(self, repo: git.Repo, repo_name: str, repo_path: str) -> Iterator[Document]:
        """Process files in the repository."""
        # Define file types to include
        text_extensions = {
            '.md', '.txt', '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h',
            '.html', '.css', '.xml', '.json', '.yaml', '.yml', '.sh', '.sql',
            '.go', '.rs', '.rb', '.php', '.cs', '.kt', '.swift', '.r', '.scala'
        }
        
        repo_path_obj = Path(repo_path)
        
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common build/dependency directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                'node_modules', '__pycache__', 'target', 'build', 'dist',
                'vendor', '.git', '.svn', '.hg'
            }]
            
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                relative_path = file_path.relative_to(repo_path_obj)
                
                # Check if file should be processed
                if (file_path.suffix.lower() in text_extensions and 
                    file_path.stat().st_size < 1024 * 1024):  # Max 1MB
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Get file history
                        commits = list(repo.iter_commits(paths=str(relative_path), max_count=1))
                        latest_commit = commits[0] if commits else None
                        
                        author = latest_commit.author.name if latest_commit else None
                        updated_at = datetime.fromtimestamp(latest_commit.committed_date) if latest_commit else None
                        
                        # Build GitHub/GitLab URL if possible
                        url = self._build_file_url(repo_name, relative_path)
                        
                        yield Document(
                            id=f"git_{repo_name}_{str(relative_path).replace('/', '_')}",
                            title=f"{repo_name}: {relative_path}",
                            content=content,
                            source=f"git_repo_{repo_name}",
                            source_type="git",
                            url=url,
                            created_at=None,  # Hard to determine creation date
                            updated_at=updated_at,
                            author=author,
                            metadata={
                                'repo_name': repo_name,
                                'file_path': str(relative_path),
                                'file_size': file_path.stat().st_size,
                                'file_extension': file_path.suffix,
                                'latest_commit_hash': latest_commit.hexsha if latest_commit else None
                            }
                        )
                        
                    except Exception as e:
                        self.logger.warning(f"Could not process file {relative_path}: {e}")
                        continue
    
    def _process_commit_history(self, repo: git.Repo, repo_name: str, max_commits: int) -> Iterator[Document]:
        """Process commit history."""
        commits = list(repo.iter_commits(max_count=max_commits))
        
        for commit in commits:
            # Build commit content
            content_parts = [
                f"Commit: {commit.hexsha[:8]}",
                f"Author: {commit.author.name} <{commit.author.email}>",
                f"Date: {datetime.fromtimestamp(commit.committed_date)}",
                f"Message: {commit.message}",
                ""
            ]
            
            # Add file changes summary
            try:
                stats = commit.stats.files
                if stats:
                    content_parts.append("Files changed:")
                    for file_path, changes in stats.items():
                        insertions = changes.get('insertions', 0)
                        deletions = changes.get('deletions', 0)
                        content_parts.append(f"- {file_path}: +{insertions}/-{deletions}")
            except Exception:
                pass  # Stats might not be available
            
            content = '\n'.join(content_parts)
            
            url = self._build_commit_url(repo_name, commit.hexsha)
            
            yield Document(
                id=f"git_{repo_name}_commit_{commit.hexsha}",
                title=f"{repo_name}: Commit {commit.hexsha[:8]}",
                content=content,
                source=f"git_repo_{repo_name}",
                source_type="git",
                url=url,
                created_at=datetime.fromtimestamp(commit.committed_date),
                updated_at=datetime.fromtimestamp(commit.committed_date),
                author=commit.author.name,
                metadata={
                    'repo_name': repo_name,
                    'commit_hash': commit.hexsha,
                    'commit_hash_short': commit.hexsha[:8],
                    'author_email': commit.author.email,
                    'files_changed': len(commit.stats.files) if hasattr(commit, 'stats') else 0
                }
            )
    
    def _build_file_url(self, repo_name: str, file_path: Path) -> Optional[str]:
        """Build URL to file in repository (GitHub/GitLab style)."""
        # This is a basic implementation - could be enhanced based on repository URL
        for repo_url in self.config.repositories:
            if repo_name in repo_url:
                if 'github.com' in repo_url:
                    base_url = repo_url.replace('.git', '') if repo_url.endswith('.git') else repo_url
                    return f"{base_url}/blob/main/{file_path}"
                elif 'gitlab.com' in repo_url:
                    base_url = repo_url.replace('.git', '') if repo_url.endswith('.git') else repo_url
                    return f"{base_url}/-/blob/main/{file_path}"
        return None
    
    def _build_commit_url(self, repo_name: str, commit_hash: str) -> Optional[str]:
        """Build URL to commit in repository."""
        for repo_url in self.config.repositories:
            if repo_name in repo_url:
                if 'github.com' in repo_url:
                    base_url = repo_url.replace('.git', '') if repo_url.endswith('.git') else repo_url
                    return f"{base_url}/commit/{commit_hash}"
                elif 'gitlab.com' in repo_url:
                    base_url = repo_url.replace('.git', '') if repo_url.endswith('.git') else repo_url
                    return f"{base_url}/-/commit/{commit_hash}"
        return None
    
    def extract_entities(self, documents: List[Document]) -> List[Entity]:
        """Extract Git-specific entities."""
        entities = super().extract_entities(documents)
        
        # Extract repository entities
        repositories = set()
        authors = set()
        file_types = set()
        
        for doc in documents:
            metadata = doc.metadata
            
            # Repository entities
            repo_name = metadata.get('repo_name')
            if repo_name:
                repositories.add(repo_name)
            
            # Author entities
            if doc.author:
                authors.add(doc.author)
            
            # File type entities
            file_extension = metadata.get('file_extension')
            if file_extension:
                file_types.add(file_extension)
        
        # Add repository entities
        for repo_name in repositories:
            repo_docs = [doc.id for doc in documents if doc.metadata.get('repo_name') == repo_name]
            entities.append(Entity(
                name=f"Repository: {repo_name}",
                type="git_repository",
                description=f"Git repository containing {len(repo_docs)} documents",
                source_documents=repo_docs,
                metadata={'repo_name': repo_name}
            ))
        
        # Add file type entities
        for file_type in file_types:
            type_docs = [doc.id for doc in documents if doc.metadata.get('file_extension') == file_type]
            entities.append(Entity(
                name=f"File Type: {file_type}",
                type="file_type",
                description=f"File type found in {len(type_docs)} documents",
                source_documents=type_docs
            ))
        
        return entities
    
    def extract_relationships(self, entities: List[Entity], documents: List[Document]) -> List[Relationship]:
        """Extract Git-specific relationships."""
        relationships = super().extract_relationships(entities, documents)
        
        entity_map = {e.name: e for e in entities}
        
        for doc in documents:
            metadata = doc.metadata
            
            # Document -> Repository relationships
            repo_name = metadata.get('repo_name')
            if repo_name:
                repo_entity_name = f"Repository: {repo_name}"
                if repo_entity_name in entity_map and doc.title in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc.title,
                        target_entity=repo_entity_name,
                        relationship_type="belongs_to",
                        source_documents=[doc.id]
                    ))
            
            # Document -> File Type relationships
            file_extension = metadata.get('file_extension')
            if file_extension:
                type_entity_name = f"File Type: {file_extension}"
                if type_entity_name in entity_map and doc.title in entity_map:
                    relationships.append(Relationship(
                        source_entity=doc.title,
                        target_entity=type_entity_name,
                        relationship_type="has_type",
                        source_documents=[doc.id]
                    ))
        
        return relationships