from fastapi import APIRouter
from app.api.v1 import auth, feedbacks, requirements, versions, notifications, systems, editing, users, roles, releases, files

api_router = APIRouter()
for module in (auth, feedbacks, requirements, versions, releases, notifications, systems, editing, users, roles, files):
    api_router.include_router(module.router)
