from fastapi import APIRouter, Request

from src.common.models import GraphResponse

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(request: Request, limit: int = 100) -> GraphResponse:
    pipelines = request.app.state.pipelines
    nodes, edges = pipelines["graph"].fetch_graph(limit=limit)
    return GraphResponse(nodes=nodes, edges=edges)


@router.get("/graph/stats")
async def get_graph_stats(request: Request) -> dict:
    pipelines = request.app.state.pipelines
    stats = pipelines["graph"].get_relationship_stats()
    return {"relationships": stats}


@router.get("/graph/document/{doc_id}")
async def get_document_relationships(
    request: Request,
    doc_id: str,
    depth: int = 1,
) -> GraphResponse:
    pipelines = request.app.state.pipelines
    depth = min(max(1, depth), 3)
    nodes, edges = pipelines["graph"].fetch_document_relationships(doc_id, depth)
    return GraphResponse(nodes=nodes, edges=edges)
