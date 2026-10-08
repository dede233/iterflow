import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDenied
from app.models.entities import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


@lru_cache
def documentation_labels() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "core" / "api_documentation.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ApiDocumentationService:
    def __init__(self, db: Session):
        self.db = db

    def read(self, user: User, schema: dict[str, Any]) -> dict[str, Any]:
        if not UserRepository(self.db).can_view_api_docs(user.id):
            raise PermissionDenied("仅超级管理员和研发负责人可以查看接口文档")

        result = deepcopy(schema)
        labels = documentation_labels()
        result["info"] = {**result["info"], **labels["info"]}
        result["info"]["title"] = "迭程 IterFlow 接口文档"
        result["tags"] = labels["tags"]
        for path, operations in result["paths"].items():
            for method, operation in operations.items():
                operation.update(
                    labels["paths"].get(path.removeprefix("/api/v1"), {}).get(method, {})
                )

        AuditService(self.db).log("API_DOCUMENTATION", None, "VIEW")
        self.db.commit()
        return result
