from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.radars import router as radars_router
from app.api.v1.routes.sources import router as sources_router
from app.api.v1.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(radars_router, prefix="/radars", tags=["radars"])
api_router.include_router(sources_router, prefix="/sources", tags=["sources"])
