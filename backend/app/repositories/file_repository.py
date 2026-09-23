from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AttachmentRelation, FileObject
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class FileRepository(BaseRepository[FileObject]):
    def __init__(self, db: Session):
        super().__init__(db, FileObject)

    def get_scoped(self, file_id: int, user_id: int, data_scope: DataScope) -> FileObject | None:
        attached = (
            select(AttachmentRelation.id)
            .where(AttachmentRelation.file_id == FileObject.id)
            .exists()
        )
        statement = select(FileObject).where(FileObject.id == file_id, ~attached)
        if data_scope is not DataScope.ALL:
            statement = statement.where(FileObject.created_by == user_id)
        return self.db.scalar(statement)

    def get_attached_to_entity(
        self, file_id: int, entity_type: str, entity_id: int
    ) -> FileObject | None:
        return self.db.scalar(
            select(FileObject)
            .join(AttachmentRelation, AttachmentRelation.file_id == FileObject.id)
            .where(
                FileObject.id == file_id,
                AttachmentRelation.entity_type == entity_type,
                AttachmentRelation.entity_id == entity_id,
            )
        )

    def has_attachments(self, file_id: int) -> bool:
        statement = select(AttachmentRelation.id).where(AttachmentRelation.file_id == file_id)
        return self.db.scalar(statement) is not None
