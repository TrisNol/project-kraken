from fastapi import APIRouter

from src.api.routers.assets import router as assets_router
from src.api.routers.chat import router as chat_router
from src.api.routers.graph import router as graph_router
from src.api.routers.index import router as index_router

api_router = APIRouter()
api_router.include_router(index_router)
api_router.include_router(chat_router)
api_router.include_router(graph_router)
api_router.include_router(assets_router)
