"""V1 API router aggregating all v1 routers."""

from fastapi import APIRouter

from routers.v1.health_router import health_router
from routers.v1.user_router import user_router
from routers.v1.ingredient_router import ingredient_router
from routers.v1.recipe_book_router import recipe_book_router
from routers.v1.recipe_router import recipe_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health_router)
v1_router.include_router(user_router)
v1_router.include_router(ingredient_router)
v1_router.include_router(recipe_book_router)
v1_router.include_router(recipe_router)
