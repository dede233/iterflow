from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AttachmentRelation, FileObject
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[FileObject]):
    def __init__(self, db: Session):
        super().__init__(db, FileObject)

    def get_scoped(self, file_id: int, user_id: int, data_scope: DataScope) -> FileObject | None:
        statement = select(FileObject).where(FileObject.id == file_id)
        if data_scope is not DataScope.ALL:
            # TODO(Phase 2): derive file access from its Feedback/Requirement/Version
            # attachment and that entity's data-scope policy. Creator ownership is a
            # deliberately temporary foundation rule, not the final authorization model.
            statement = statement.where(FileObject.created_by == user_id)
        return self.db.scalar(statement)

    def has_attachments(self, file_id: int) -> bool:
        statement = select(AttachmentRelation.id).where(AttachmentRelation.file_id == file_id)
        return self.db.scalar(statement) is not None
