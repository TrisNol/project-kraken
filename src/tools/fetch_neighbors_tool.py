from typing import List

from haystack import Document, component
from neo4j import GraphDatabase


@component
class FetchNeighbors:
    """Fetch related documents from the graph via REFERENCES relationships to expand context."""

    def __init__(
        self,
        neo4j_url: str,
        neo4j_username: str,
        neo4j_password: str,
        neo4j_database: str = "neo4j",
    ):
        self.neo4j_url = neo4j_url
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database

    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document]) -> dict:
        if not documents:
            return {"documents": []}

        driver = GraphDatabase.driver(
            self.neo4j_url, auth=(self.neo4j_username, self.neo4j_password)
        )
        try:
            seen_ids = set()
            # Track IDs of input documents to avoid duplicates
            for doc in documents:
                doc_id = doc.meta.get("id", "")
                if doc_id:
                    seen_ids.add(doc_id)

            neighbor_docs = []
            with driver.session(database=self.neo4j_database) as session:
                for doc in documents:
                    doc_id = doc.meta.get("id", "")
                    if not doc_id:
                        continue

                    result = session.run(
                        """
                        MATCH (d:Document {id: $doc_id})-[:REFERENCES]-(neighbor:Document)
                        OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(neighbor)
                        RETURN neighbor, collect(c.content) AS chunks
                        """,
                        doc_id=doc_id,
                    )

                    for record in result:
                        neighbor_node = record["neighbor"]
                        metadata = dict(neighbor_node)
                        n_id = metadata.get("id", "")
                        if n_id in seen_ids:
                            continue
                        seen_ids.add(n_id)
                        chunks = record["chunks"]
                        content = (
                            "\n---\n".join(c for c in chunks if c)
                            if chunks
                            else metadata.get("title", "")
                        )
                        neighbor_docs.append(
                            Document(content=content, meta=metadata)
                        )

            return {"documents": documents + neighbor_docs}
        finally:
            driver.close()
