"""Dialect-specific UTC storage, with PostgreSQL behaviour unchanged."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is not None and dialect.name == "mysql":
            if value.tzinfo is None:
                raise ValueError("MySQL timestamps must be timezone-aware")
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and dialect.name == "mysql":
            return value.replace(tzinfo=UTC)
        return value


class ExactIdentifier(TypeDecorator[str]):
    """MySQL binary identifiers preserve PG case and trailing-space equality."""

    impl = String
    cache_ok = True

    def __init__(self, length, *, overflow_bytes=0):
        super().__init__(length=length)
        self.length = length
        self.overflow_bytes = overflow_bytes

    def load_dialect_impl(self, dialect):
        from sqlalchemy.dialects.mysql import VARBINARY

        # File keys need overflow space so a permissive raw SQL writer cannot
        # truncate an oversized 4-byte UTF-8 key into a valid 500-character key
        # before the database guard runs. The accepted domain is unchanged.
        capacity = self.length * 4 + self.overflow_bytes
        return dialect.type_descriptor(VARBINARY(capacity))

    def process_bind_param(self, value, dialect):
        return value.encode("utf-8") if value is not None else None

    def process_result_value(self, value, dialect):
        return value.decode("utf-8") if value is not None else None

    class comparator_factory(TypeDecorator.Comparator):
        def _text(self):
            from sqlalchemy import String, cast

            return cast(self.expr, String()).collate("utf8mb4_bin")

        def like(self, other, escape=None):
            return self._text().like(other, escape=escape)

        def ilike(self, other, escape=None):
            return self._text().ilike(other, escape=escape)
