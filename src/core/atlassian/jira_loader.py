from atlassian import Jira

from haystack import Document
from src.common.models import JiraMetadata, DocumentSourceType
from src.core.atlassian import convert_to_markdown


class JiraLoader:
    def __init__(self, url, username, api_key, projects):
        self.url = url
        self.username = username
        self.api_key = api_key
        self.projects = projects
        self.client = Jira(
            url=self.url, username=self.username, password=self.api_key, cloud=True
        )

    async def load(self):
        all_issues = []
        for project in self.projects:
            issues = self.client.jql(
                f"project = {project}",
            )
            all_issues.extend(issues["issues"])

        documents = []
        for issue in all_issues:
            content = issue["fields"]["description"] or ""
            if (
                hasattr(issue["fields"], "comment")
                and issue["fields"]["comment"]["comments"]
            ):
                comments = "\n".join(
                    [
                        comment["body"]
                        for comment in issue["fields"]["comment"]["comments"]
                    ]
                )
                content += "\n\nComments:\n" + comments
            metadata = JiraMetadata(
                source=f"{self.url}/browse/{issue['key']}",
                type=DocumentSourceType.JIRA,
                last_updated=issue["fields"]["updated"],
                issue_key=issue["key"],
                project_key=project,
            )
            documents.append(Document(content=convert_to_markdown(content), meta=metadata.model_dump()))
        return documents
