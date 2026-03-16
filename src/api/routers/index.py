from fastapi import APIRouter, Request

router = APIRouter(tags=["index"])


@router.get("/index/stats")
async def get_index_stats(request: Request) -> dict:
    pipelines = request.app.state.pipelines
    return {"count": pipelines["index"].get_index_stats()}


@router.post("/index/create")
async def create_index(request: Request) -> dict[str, str]:
    loaders = request.app.state.loaders
    pipelines = request.app.state.pipelines

    docs = []
    for loader in loaders.values():
        if loader is None:
            continue
        loader_docs = await loader.load()
        docs.extend(loader_docs)

    if not docs:
        return {"status": "no documents to index"}

    pipelines["index"].create_index(docs)
    return {"status": "index created"}


@router.post("/index/clear")
async def clear_index(request: Request) -> dict[str, str]:
    pipelines = request.app.state.pipelines
    chat_memory = request.app.state.chat_memory

    pipelines["index"].clear_index()
    chat_memory.clear_all()
    return {"status": "index cleared"}
