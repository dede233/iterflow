# ruff: noqa: RUF001
from datetime import UTC, datetime
from types import SimpleNamespace

from app.core.config import get_settings
from app.models.entities import Requirement
from app.services.delivery_service import DeliveryService, _safe_subject


def event(**overrides):
    values = {
        "id": "event-id",
        "entity_type": "FEEDBACK",
        "entity_id": 12,
        "action": "STATUS_ACCEPTED",
        "created_at": datetime(2026, 11, 18, 8, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def delivery(user_id=2):
    return SimpleNamespace(id="delivery-id", user_id=user_id)


def test_verification_mail_has_branded_html_and_plain_text(monkeypatch):
    monkeypatch.setattr("app.services.delivery_service.verification_code", lambda _: "123456")
    settings = get_settings()
    monkeypatch.setattr(settings, "app_public_url", "https://iterflow.example.test")
    service = DeliveryService(db=None)

    message = service._message(event(action="VERIFY_EMAIL"), delivery(), "user@example.test")

    assert message["Subject"] == "迭程 IterFlow｜验证通知邮箱"
    assert message.get_body(preferencelist=("plain",)).get_content().find("123456") >= 0
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "迭程" in html and "验证您的通知邮箱" in html and "15 分钟内有效" in html
    assert 'href="https://iterflow.example.test/#/profile#mail-notifications"' in html
    assert "打开个人中心" in html


def test_feedback_acceptance_mail_names_submitter_and_escapes_title(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_public_url", "https://iterflow.example.test")
    feedback = SimpleNamespace(
        title='登录 <script>alert("x")</script>',
        created_at=datetime(2026, 11, 17, 2, 30, tzinfo=UTC),
        submitter_id=2,
    )
    service = DeliveryService(db=SimpleNamespace(get=lambda model, object_id: feedback))

    message = service._message(event(), delivery(user_id=2), "user@example.test")

    assert "反馈已受理" in message["Subject"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert '您于 2026年11月17日 10:30 提交的反馈《登录 <script>alert("x")</script>》已受理' in plain
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "登录 &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "<script>alert(" not in html
    assert 'href="https://iterflow.example.test/#/feedbacks/12"' in html
    assert "查看反馈详情" in html


def test_feedback_acceptance_to_other_recipients_does_not_call_them_submitter(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_public_url", "https://iterflow.example.test")
    feedback = SimpleNamespace(
        title="反馈标题",
        created_at=datetime(2026, 11, 17, 2, 30, tzinfo=UTC),
        submitter_id=1,
    )
    service = DeliveryService(db=SimpleNamespace(get=lambda model, object_id: feedback))

    message = service._message(event(), delivery(user_id=2), "recipient@example.test")

    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "反馈《反馈标题》于 2026年11月18日 16:00 更新：反馈已受理" in plain
    assert "您提交的反馈" not in plain


def test_requirement_mail_includes_title_change_and_view_link(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_public_url", "https://iterflow.example.test")
    requirement = SimpleNamespace(title="导出报表优化", created_at=None, submitter_id=1)
    service = DeliveryService(
        db=SimpleNamespace(
            get=lambda model, object_id: requirement if model is Requirement else None
        )
    )
    notification = event(
        entity_type="REQUIREMENT",
        entity_id=25,
        action="STATUS_TESTING",
    )

    message = service._message(notification, delivery(user_id=2), "recipient@example.test")

    assert "需求已提交验收" in message["Subject"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "需求《导出报表优化》于 2026年11月18日 16:00 更新：需求已提交验收。" in plain
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "导出报表优化" in html
    assert 'href="https://iterflow.example.test/#/requirements/25"' in html
    assert "查看需求详情" in html


def test_mail_subject_removes_newlines():
    assert _safe_subject("标题\r\n伪造字段") == "标题 伪造字段"
