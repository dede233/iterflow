"""Explicit business-system setup for disposable integration fixtures."""

from uuid import uuid4

from sqlalchemy import MetaData, Table
from sqlalchemy.orm import Session, registry

from app.models.entities import BusinessSystem, Version


def create_test_system(engine):
    with Session(engine, expire_on_commit=False) as db:
        item = BusinessSystem(code="BIND-" + uuid4().hex[:12], name="隔离验收业务系统")
        db.add(item)
        db.commit()
        return item.id


def historical_version(engine, mapper_registry=None):
    """Map the actual old schema when testing migrations before system_id existed."""
    mapper_registry = mapper_registry or registry()
    table = Table("rd_version", MetaData(), autoload_with=engine)
    for column in table.columns:
        if column.name in Version.__table__.c:
            column.default = Version.__table__.c[column.name].default
            # Keep application bind processors (MySQL exact identifiers are VARBINARY).
            column.type = Version.__table__.c[column.name].type
    model = type("HistoricalVersion", (), {})
    mapper_registry.map_imperatively(model, table)
    return model
