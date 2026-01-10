from fastapi import APIRouter

from routers.v1.user_router import user_router
from routers.v1.health_router import health_router

v1_router = APIRouter(prefix="/v1", tags=["v1"])

v1_router.include_router(user_router)
v1_router.include_router(health_router)
