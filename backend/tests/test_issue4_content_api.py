import pytest
from sqlalchemy import func, select
from test_requirement_api import _create_req
from test_requirement_api import req_api as _shared_req_api

from app.models.entities import CollaborationEvent, OperationLog, Requirement


@pytest.fixture
def content_api(tmp_path):
    yield from _shared_req_api.__wrapped__(tmp_path)


@pytest.mark.parametrize(
    "title", ["", "  ", "\u200b\ufeff", "一", "\x01\x02", "\x00\x00", "有效标题\x00"]
)
def test_reject_empty_create_and_edit_without_writes(content_api, title):
    client, db, headers, _ = content_api
    item = _create_req(client, headers["boss"])
    before = [
        db.scalar(select(func.count()).select_from(m))
        for m in (Requirement, OperationLog, CollaborationEvent)
    ]
    for method, path, body in [
        (
            client.post,
            "/api/v1/requirements",
            {"title": title, "description": "有效描述", "requirement_type": "FEATURE"},
        ),
        (
            client.patch,
            f"/api/v1/requirements/{item['id']}",
            {"title": title, "description": "", "revision": item["revision"]},
        ),
    ]:
        result = method(path, headers=headers["boss"], json=body)
        assert result.status_code == 422, result.text
    db.expire_all()
    assert [
        db.scalar(select(func.count()).select_from(m))
        for m in (Requirement, OperationLog, CollaborationEvent)
    ] == before
    latest = client.get(f"/api/v1/requirements/{item['id']}", headers=headers["boss"]).json()
    assert latest["title"] == item["title"] and latest["revision"] == item["revision"]


@pytest.mark.parametrize(
    "description,format",
    [
        ("", "PLAIN"),
        ("  ", "PLAIN"),
        ("<p><br></p>", "HTML"),
        ("<script>alert(1)</script>", "HTML"),
        ("\x01\x02", "PLAIN"),
        ("\x00\x00", "PLAIN"),
        ("正常描述\x00", "PLAIN"),
        ("<p>正常描述\x00</p>", "HTML"),
    ],
)
def test_empty_description_edit_is_rejected(content_api, description, format):
    client, _, headers, _ = content_api
    item = _create_req(client, headers["boss"])
    result = client.patch(
        f"/api/v1/requirements/{item['id']}",
        headers=headers["boss"],
        json={
            "description": description,
            "description_format": format,
            "revision": item["revision"],
        },
    )
    assert result.status_code == 422, result.text
    latest = client.get(f"/api/v1/requirements/{item['id']}", headers=headers["boss"]).json()
    assert latest["description"] == item["description"] and latest["revision"] == item["revision"]


def test_html_sanitized_snapshot_and_format_change_invalidates_confirmation(content_api):
    client, db, headers, _ = content_api
    item = _create_req(client, headers["boss"], description="<strong>旧文字</strong>")
    assert item["description_format"] == "PLAIN"
    confirmed = client.post(
        f"/api/v1/requirements/{item['id']}/workflow",
        headers=headers["boss"],
        json={"action": "CONFIRM", "revision": item["revision"]},
    )
    assert confirmed.status_code == 200
    result = client.patch(
        f"/api/v1/requirements/{item['id']}",
        headers=headers["boss"],
        json={"description_format": "HTML", "revision": confirmed.json()["revision"]},
    )
    assert result.status_code == 200, result.text
    flow = client.get(f"/api/v1/requirements/{item['id']}/workflow", headers=headers["boss"]).json()
    assert flow["needs_confirmation"] is True
    assert flow["records"][0]["detail"]["description_format"] == "PLAIN"
    result = client.patch(
        f"/api/v1/requirements/{item['id']}",
        headers=headers["boss"],
        json={
            "description": '<p onclick="evil()">新描述<script>evil()</script></p>',
            "description_format": "HTML",
            "revision": result.json()["revision"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["description"] == "<p>新描述</p>"
    db.expire_all()
    assert db.get(Requirement, item["id"]).description == "<p>新描述</p>"


def test_title_edit_preserves_unchanged_plain_content_confirmation(content_api):
    client, _, headers, _ = content_api
    description = "  旧文字描述\n<strong>纯文本</strong>  "
    item = _create_req(client, headers["boss"], description=description)
    confirmed = client.post(
        f"/api/v1/requirements/{item['id']}/workflow",
        headers=headers["boss"],
        json={"action": "CONFIRM", "revision": item["revision"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    result = client.patch(
        f"/api/v1/requirements/{item['id']}",
        headers=headers["boss"],
        json={
            "title": "只修改需求标题",
            "description": description,
            "description_format": "PLAIN",
            "revision": confirmed.json()["revision"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["description"] == description
    assert result.json()["description_format"] == "PLAIN"
    flow = client.get(f"/api/v1/requirements/{item['id']}/workflow", headers=headers["boss"]).json()
    assert flow["needs_confirmation"] is False
