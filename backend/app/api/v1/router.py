from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.collection_runs import router as collection_runs_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.intelligence import analyses_router
from app.api.v1.routes.intelligence import router as intelligence_router
from app.api.v1.routes.memory import bookmark_router, memory_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.radars import router as radars_router
from app.api.v1.routes.sources import router as sources_router
from app.api.v1.routes.users import router as users_router
from app.api.v1.routes.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(radars_router, prefix="/radars", tags=["radars"])
api_router.include_router(sources_router, prefix="/sources", tags=["sources"])
api_router.include_router(
    collection_runs_router,
    prefix="/collection-runs",
    tags=["collection-runs"],
)
api_router.include_router(intelligence_router, prefix="/intelligence", tags=["intelligence"])
api_router.include_router(analyses_router, prefix="/analyses", tags=["analyses"])
api_router.include_router(bookmark_router, prefix="/bookmarks", tags=["bookmarks"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(websocket_router, prefix="/ws", tags=["websocket"])
