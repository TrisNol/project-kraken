import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.common.models import DocumentSourceType

router = APIRouter(tags=["assets"])


@router.get("/icon")
async def get_icon(type: DocumentSourceType) -> FileResponse:
    filename = None
    if type == DocumentSourceType.JIRA:
        filename = "jira.png"
    elif type == DocumentSourceType.CONFLUENCE:
        filename = "confluence.png"
    elif type == DocumentSourceType.GITHUB:
        filename = "github.png"

    if not filename:
        raise HTTPException(status_code=404, detail="Icon not found")

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "..", "..", "assets", filename)
    path = os.path.normpath(path)

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Icon not found")

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(path, media_type="image/png", headers=headers)
