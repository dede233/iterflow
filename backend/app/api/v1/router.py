from fastapi import APIRouter

from app.api.v1 import (
    audits,
    auth,
    dashboard,
    editing,
    feedbacks,
    files,
    notifications,
    releases,
    requirements,
    roles,
    systems,
    users,
    versions,
)

api_router = APIRouter()
for module in (
    auth,
    dashboard,
    audits,
    feedbacks,
    requirements,
    versions,
    releases,
    notifications,
    systems,
    editing,
    users,
    roles,
    files,
):
    api_router.include_router(module.router)
