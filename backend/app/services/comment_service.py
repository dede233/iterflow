from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Comment
from app.services.audit_service import AuditService


class CommentService:
    """Minimal entity comment closure (Phase 3 uses it for FEEDBACK only).

    Callers are responsible for authorizing access to the target entity (data
    scope + view permission) before listing or creating comments here.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[Comment]:
        return list(
            self.db.scalars(
                select(Comment)
                .where(Comment.entity_type == entity_type, Comment.entity_id == entity_id)
                .order_by(Comment.created_at.asc(), Comment.id.asc())
            ).all()
        )

    def create_for_entity(
        self, entity_type: str, entity_id: int, content: str, operator_id: int
    ) -> Comment:
        comment = Comment(
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(comment)
        self.db.flush()
        self.audit.log(
            entity_type,
            entity_id,
            "COMMENT_CREATE",
            after={"comment_id": comment.id},
        )
        self.db.commit()
        self.db.refresh(comment)
        return comment
