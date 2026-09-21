from unittest.mock import Mock

import pytest
from sqlalchemy.dialects.postgresql import JSONB, dialect
from sqlalchemy.orm import Session

from app.models.entities import Dictionary, DictionaryItem, OperationLog
from app.models.enums import DataScope
from app.repositories.dictionary_repository import (
    DictionaryItemRepository,
    DictionaryRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.dictionary import (
    DictionaryCreate,
    DictionaryItemCreate,
    DictionaryItemUpdate,
    DictionaryUpdate,
)


def test_dictionary_models_and_schemas_expose_foundation_fields():
    assert Dictionary.__tablename__ == "sys_dictionary"
    assert DictionaryItem.__tablename__ == "sys_dictionary_item"
    assert {"code", "name", "description", "enabled", "revision"}.issubset(
        Dictionary.__table__.c.keys()
    )
    assert {
        "dictionary_id",
        "code",
        "label",
        "value",
        "sort_order",
        "enabled",
        "revision",
    }.issubset(DictionaryItem.__table__.c.keys())

    dictionary = DictionaryCreate(code="PRIORITY_REASON", name="优先级原因")
    item = DictionaryItemCreate(
        dictionary_id=1,
        code="CUSTOMER_BLOCKED",
        label="客户阻塞",
        value="CUSTOMER_BLOCKED",
    )
    assert dictionary.enabled is True
    assert item.sort_order == 0
    assert DictionaryUpdate(revision=1, enabled=False).enabled is False
    assert DictionaryItemUpdate(revision=1, sort_order=10).sort_order == 10


def test_dictionary_repositories_are_bound_to_the_expected_models():
    db = Mock(spec=Session)
    assert DictionaryRepository(db).model is Dictionary
    assert DictionaryItemRepository(db).model is DictionaryItem


def test_operation_log_uses_jsonb_on_postgresql_and_records_user_agent():
    postgresql_dialect = dialect()

    assert isinstance(
        OperationLog.__table__.c.before_data.type.dialect_impl(postgresql_dialect), JSONB
    )
    assert isinstance(
        OperationLog.__table__.c.after_data.type.dialect_impl(postgresql_dialect), JSONB
    )
    assert OperationLog.__table__.c.user_agent.type.length == 512


def test_team_scope_in_persisted_roles_is_rejected_explicitly():
    db = Mock(spec=Session)
    db.scalars.return_value.all.return_value = [DataScope.TEAM]

    with pytest.raises(RuntimeError, match="reserved"):
        UserRepository(db).data_scope(user_id=1)


def test_reserved_team_scope_is_rejected_even_when_an_all_role_exists():
    db = Mock(spec=Session)
    db.scalars.return_value.all.return_value = [DataScope.TEAM, DataScope.ALL]

    with pytest.raises(RuntimeError, match="reserved"):
        UserRepository(db).data_scope(user_id=1)
