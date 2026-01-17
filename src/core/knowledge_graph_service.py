from typing import List, Tuple
from neo4j import GraphDatabase

from src.common.models import (
    DocumentSourceType,
    GraphNode,
    GraphEdge,
    JiraMetadata,
    ConfluenceMetadata,
    GitHubMetadata,
)


class KnowledgeGraphService:
    """Service for fetching and processing knowledge graph data from Neo4j."""

    def __init__(self, neo4j_url: str, neo4j_username: str, neo4j_password: str, neo4j_database: str = "neo4j"):
        """
        Initialize the knowledge graph service.

        Args:
            neo4j_url: URL of the Neo4j instance
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            neo4j_database: Neo4j database name (default: "neo4j")
        """
        self.neo4j_url = neo4j_url
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database

    def fetch_graph(self, limit: int = 100) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """
        Fetch nodes and edges from Neo4j.

        Args:
            limit: Maximum number of nodes to fetch

        Returns:
            Tuple of (nodes, edges) where nodes is a list of GraphNode and edges is a list of GraphEdge
        """
        driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_username, self.neo4j_password)
        )

        nodes = []
        edges = []

        try:
            with driver.session(database=self.neo4j_database) as session:
                # Fetch all document nodes
                result = session.run("""
                    MATCH (doc:Document)
                    OPTIONAL MATCH (doc)-[rel]->(target:Document)
                    RETURN doc, collect({rel: rel, target: target}) as relationships
                    LIMIT $limit
                """, limit=limit)

                for record in result:
                    doc = record["doc"]
                    doc_id = doc.element_id
                    metadata_dict = dict(doc)

                    # Extract type and create appropriate metadata
                    doc_type = metadata_dict.get("type", "JIRA")

                    # Build title and metadata based on type
                    title, metadata = self._build_node_metadata(doc_type, metadata_dict)
                    url = metadata_dict.get("source", "#")

                    nodes.append(GraphNode(
                        id=doc_id,
                        title=title,
                        url=url,
                        type=doc_type,
                        metadata=metadata
                    ))

                    # Process relationships
                    for rel_data in record["relationships"]:
                        if rel_data["rel"] and rel_data["target"]:
                            edges.append(GraphEdge(
                                source=doc_id,
                                target=rel_data["target"].element_id,
                                relationship=rel_data["rel"].type
                            ))

        finally:
            driver.close()

        return nodes, edges

    def _build_node_metadata(
        self, doc_type: str, metadata_dict: dict
    ) -> Tuple[str, JiraMetadata | ConfluenceMetadata | GitHubMetadata]:
        """
        Build title and metadata based on document type.

        Args:
            doc_type: Type of the document
            metadata_dict: Dictionary containing document metadata

        Returns:
            Tuple of (title, metadata)
        """
        if doc_type == "JIRA":
            title = metadata_dict.get("issue_key", "Jira")
            metadata = JiraMetadata(
                source=metadata_dict.get("source", ""),
                type=DocumentSourceType.JIRA,
                last_updated=metadata_dict.get("last_updated", ""),
                issue_key=metadata_dict.get("issue_key", ""),
                project_key=metadata_dict.get("project_key", ""),
                title=metadata_dict.get("title", "")
            )
        elif doc_type == "CONFLUENCE":
            space_key = metadata_dict.get("space_key", "")
            doc_title = metadata_dict.get("title", "")
            title = f"{space_key}: {doc_title}" if space_key and doc_title else "Confluence"
            metadata = ConfluenceMetadata(
                source=metadata_dict.get("source", ""),
                type=DocumentSourceType.CONFLUENCE,
                last_updated=metadata_dict.get("last_updated", ""),
                page_id=metadata_dict.get("page_id", ""),
                space_key=space_key,
                title=doc_title
            )
        elif doc_type == "GITHUB":
            repo_name = metadata_dict.get("repo_name", "")
            file_path = metadata_dict.get("file_path", "")
            title = f"{repo_name}/{file_path}" if repo_name and file_path else "GitHub"
            metadata = GitHubMetadata(
                source=metadata_dict.get("source", ""),
                type=DocumentSourceType.GITHUB,
                last_updated=metadata_dict.get("last_updated", ""),
                repo_name=repo_name,
                file_path=file_path,
                commit_hash=metadata_dict.get("commit_hash", ""),
                ref=metadata_dict.get("ref", "main")
            )
        else:
            # Default to JIRA type if unknown
            title = "Document"
            metadata = JiraMetadata(
                source=metadata_dict.get("source", ""),
                type=DocumentSourceType.JIRA,
                last_updated=metadata_dict.get("last_updated", ""),
                issue_key="",
                project_key="",
                title=title
            )

        return title, metadata
