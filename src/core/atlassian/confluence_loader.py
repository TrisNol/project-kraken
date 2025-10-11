from atlassian import Confluence

from haystack import Document
from src.common.models import ConfluenceMetadata, DocumentSourceType


def map_to_confluence_doc(doc: Document) -> Document:
    meta: ConfluenceMetadata = ConfluenceMetadata(
        source=doc.meta.get("source"),
        type=DocumentSourceType.CONFLUENCE,
        last_updated=doc.meta.get("when"),
        page_id=doc.meta.get("id"),
        space_key=doc.meta.get("source").split("/")[5],
    )
    return Document(content=doc.content, meta=meta.model_dump())


class ConfluenceLoader:
    def __init__(
        self,
        url: str,
        username: str,
        api_key: str,
        space_key: str,
        include_attachments: bool = False,
        limit: int = 100,
    ):
        self.confluence = Confluence(url=url, username=username, password=api_key)
        self.space_key = space_key
        self.include_attachments = include_attachments
        self.limit = limit

    async def load(self):
        cql = f'space="{self.space_key}" order by lastmodified desc'
        results = self.confluence.cql(cql, limit=self.limit)
        documents = []
        for result in results.get("results", []):
            if "id" not in result.get("content", {}):
                continue
            content_id = result["content"]["id"]
            title = result["content"]["title"]
            body = self.confluence.get_page_by_id(content_id, expand="body.storage")
            page_content = body["body"]["storage"]["value"]
            metadata = {
                "source": f"{self.confluence.url}/spaces/{self.space_key}/pages/{content_id}",
                "when": result["lastModified"],
                "id": content_id,
            }
            document = Document(content=page_content, meta=metadata)
            documents.append(map_to_confluence_doc(document))

            if self.include_attachments:
                attachments = self.confluence.get_attachments(content_id)
                for attachment in attachments.get("results", []):
                    attachment_content = self.confluence.get_attachment_data(
                        attachment["id"]
                    )
                    attachment_metadata = {
                        "source": f"{self.confluence.url}/spaces/{self.space_key}/pages/{content_id}/attachments/{attachment['id']}",
                        "when": attachment["version"]["when"],
                        "id": attachment["id"],
                    }
                    attachment_document = Document(
                        content=attachment_content.decode("utf-8", errors="ignore"),
                        meta=attachment_metadata,
                    )
                    documents.append(map_to_confluence_doc(attachment_document))
        return documents
