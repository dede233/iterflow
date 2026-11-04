from typing import Literal

from sqlalchemy.orm import Session

from app.repositories.filter_options_repository import FilterOptionsRepository
from app.repositories.user_repository import UserRepository


class FilterOptionsService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)
        self.repo = FilterOptionsRepository(db)

    def list(
        self,
        kind: Literal["participants", "requirement_versions", "owners"],
        user_id: int,
        keyword: str,
        page: int,
        page_size: int,
        selected_id: int | None,
    ) -> dict:
        scope = self.users.data_scope(user_id)
        if kind == "participants":
            query = self.repo.participants(user_id, scope)
        elif kind == "owners":
            query = self.repo.owners(user_id, scope)
        else:
            codes = self.users.permission_codes(user_id)
            query = self.repo.requirement_versions(
                user_id, scope, bool(codes.intersection({"*", "rd.version.view"}))
            )
        items, total = self.repo.page(query, keyword, page, page_size, selected_id)
        return {"items": items, "total": total, "page": page, "page_size": page_size}
