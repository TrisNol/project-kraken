from typing import List

from haystack import Document, component


@component
class FilterDocs:
    """Filter documents based on relevance to the user's query using keyword overlap scoring."""

    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document], query: str) -> dict:
        if not documents:
            return {"documents": []}

        query_terms = set(query.lower().split())
        scored_docs = []
        for doc in documents:
            content = (doc.content or "").lower()
            meta_text = " ".join(
                str(v) for v in doc.meta.values() if v is not None
            ).lower()
            text = content + " " + meta_text
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return {"documents": [doc for _, doc in scored_docs]}
