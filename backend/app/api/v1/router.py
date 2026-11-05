from fastapi import APIRouter

from app.api.v1 import (
    audits,
    auth,
    collaboration,
    dashboard,
    docs,
    editing,
    feedbacks,
    files,
    filter_options,
    mail,
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
    # Static filter paths must precede /requirements/{requirement_id}/participants.
    filter_options,
    collaboration,
    auth,
    dashboard,
    docs,
    audits,
    feedbacks,
    requirements,
    versions,
    releases,
    notifications,
    mail,
    systems,
    editing,
    users,
    roles,
    files,
):
    api_router.include_router(module.router)
