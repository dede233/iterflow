from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.repositories.base import BaseRepository


class LocalBase(DeclarativeBase):
    pass


class RevisionedRecord(LocalBase):
    __tablename__ = "test_revisioned_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str]


def test_revision_update_is_atomic_and_rejects_stale_revision():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    LocalBase.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(RevisionedRecord(id=1, revision=1, value="initial"))
        session.commit()
        repository = BaseRepository(session, RevisionedRecord)

        assert repository.update_with_revision(1, 1, {"value": "first"})
        session.commit()
        assert not repository.update_with_revision(1, 1, {"value": "stale"})
        session.commit()

        record = session.get(RevisionedRecord, 1)
        assert record is not None
        assert record.revision == 2
        assert record.value == "first"
