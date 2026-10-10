from collaboration_acceptance import (
    exercise_assignment_scope_and_notifications,
    exercise_concurrent_assignment,
    exercise_database_guards,
    exercise_invalid_and_rollback,
    exercise_publish_and_status_rollback,
    exercise_role_revocation,
)
from test_acceptance import mysql_api as mysql_api


def test_collaboration_scope_notifications_mysql(mysql_api):
    exercise_assignment_scope_and_notifications(mysql_api)


def test_collaboration_rollback_mysql(mysql_api, monkeypatch):
    exercise_invalid_and_rollback(mysql_api, monkeypatch)


def test_collaboration_concurrent_mysql(mysql_api):
    exercise_concurrent_assignment(mysql_api)


def test_collaboration_publish_and_status_rollback_mysql(mysql_api, monkeypatch):
    exercise_publish_and_status_rollback(mysql_api, monkeypatch)


def test_collaboration_revocation_mysql(mysql_api):
    exercise_role_revocation(mysql_api)


def test_collaboration_database_guards_mysql(mysql_api):
    exercise_database_guards(mysql_api)
