"""V1 API router aggregating all v1 routers."""

from fastapi import APIRouter
from routers.v1.activity_router import activity_router
from routers.v1.admin_router import admin_router
from routers.v1.calendar_router import calendar_router
from routers.v1.chat_router import chat_router
from routers.v1.cooking_log_router import cooking_log_router
from routers.v1.friends_router import friends_router
from routers.v1.health_router import health_router
from routers.v1.import_router import import_router
from routers.v1.invitations_router import invitations_router
from routers.v1.invite_links_router import invite_links_router
from routers.v1.meal_event_router import meal_event_router
from routers.v1.meal_router import book_meal_router, meal_router
from routers.v1.pantry_router import pantry_router
from routers.v1.parser_router import parser_router
from routers.v1.recipe_book_router import recipe_book_router
from routers.v1.recipe_router import recipe_router
from routers.v1.recurrence_rule_router import recurrence_rule_router
from routers.v1.search_router import search_router
from routers.v1.shopping_list_router import shopping_list_router
from routers.v1.timer_router import timer_router
from routers.v1.units_router import units_router
from routers.v1.user_router import user_router

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(admin_router)
v1_router.include_router(activity_router)
v1_router.include_router(calendar_router)
v1_router.include_router(chat_router)
v1_router.include_router(cooking_log_router)
v1_router.include_router(health_router)
v1_router.include_router(user_router)
v1_router.include_router(friends_router)
v1_router.include_router(recipe_book_router)
v1_router.include_router(recipe_router)
v1_router.include_router(search_router)
v1_router.include_router(meal_event_router)
v1_router.include_router(meal_router)
v1_router.include_router(book_meal_router)
v1_router.include_router(recurrence_rule_router)
v1_router.include_router(pantry_router)
v1_router.include_router(shopping_list_router)
v1_router.include_router(timer_router)
v1_router.include_router(import_router)
v1_router.include_router(parser_router)
v1_router.include_router(invitations_router)
v1_router.include_router(invite_links_router)
v1_router.include_router(units_router)
