"""V1 API router aggregating all v1 routers."""

from fastapi import APIRouter
from routers.v1.friends_router import friends_router
from routers.v1.health_router import health_router
from routers.v1.import_router import import_router
from routers.v1.ingredient_router import ingredient_router
from routers.v1.meal_event_router import meal_event_router
from routers.v1.parser_router import parser_router
from routers.v1.recipe_book_router import recipe_book_router
from routers.v1.recipe_router import recipe_router
from routers.v1.shopping_list_router import shopping_list_router
from routers.v1.timer_router import timer_router
from routers.v1.user_router import user_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health_router)
v1_router.include_router(user_router)
v1_router.include_router(friends_router)
v1_router.include_router(ingredient_router)
v1_router.include_router(recipe_book_router)
v1_router.include_router(recipe_router)
v1_router.include_router(meal_event_router)
v1_router.include_router(shopping_list_router)
v1_router.include_router(timer_router)
v1_router.include_router(import_router)
v1_router.include_router(parser_router)
