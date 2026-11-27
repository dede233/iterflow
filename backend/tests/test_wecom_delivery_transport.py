import json
import ssl
from collections import deque
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from app.core import wecom
from app.core.config import Settings

CONFIGURATION = {
    "app_env": "test",
    "app_public_url": "https://iterflow.example.test/app",
    "wecom_enabled": True,
    "wecom_corp_id": "corporation",
    "wecom_agent_id": 1000002,
    "wecom_agent_secret": "stub/secret+&",
    "wecom_allowlist": "Member_1, member_2",
}
DETAIL = "https://iterflow.example.test/app/#/feedbacks/41?notification=delivery-id"
TOKEN = {"errcode": 0, "access_token": "stub/token+&", "expires_in": 7200}


def configuration(**changes):
    return Settings(_env_file=None, **(CONFIGURATION | changes))


@pytest.fixture
def transport(monkeypatch):
    replies = deque()
    requests = []

    def open_connection(host, port, *, timeout, context):
        assert host == "qyapi.weixin.qq.com" and port == 443
        assert 0 < timeout <= 5
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        connection = Mock()
        reply = replies.popleft()
        connection.request.side_effect = lambda *args, **kwargs: requests.append((args, kwargs))
        if isinstance(reply, OSError):
            connection.connect.side_effect = reply
        else:
            status, body = reply
            response = MagicMock(status=status)
            response.__enter__.return_value = response
            if isinstance(body, OSError):
                response.read.side_effect = body
            else:
                response.read.return_value = json.dumps(body).encode() if body else b""
            connection.getresponse.return_value = response
        return connection

    monkeypatch.setattr(wecom, "HTTPSConnection", open_connection)
    return replies, requests


@pytest.mark.parametrize(
    "changes",
    [
        {"wecom_allowlist": ""},
        {"wecom_allowlist": "@all"},
        {"wecom_allowlist": "Member_1|member_2"},
        {"wecom_agent_id": 0},
        {"wecom_corp_id": ""},
        {"wecom_corp_id": " "},
        {"wecom_corp_id": "x" * 129},
        {"wecom_agent_secret": None},
        {"app_public_url": "https://user:password@iterflow.example.test"},
        {"app_public_url": "https://iterflow.example.test:bad"},
        {"app_public_url": "https://iterflow.example.test/app#existing"},
        {
            "app_env": "production",
            "allowed_hosts": "iterflow.example.test",
            "app_public_url": "http://iterflow.example.test",
        },
    ],
)
def test_wecom_configuration_rejects_unsafe_or_missing_values(changes):
    with pytest.raises(ValidationError) as error:
        configuration(**changes)
    assert CONFIGURATION["wecom_agent_secret"] not in str(error.value)


def test_wecom_configuration_allows_disabled_defaults_and_exact_test_members():
    settings = configuration(wecom_enabled=False, wecom_allowlist="", wecom_agent_id=0)
    assert not settings.wecom_enabled
    assert configuration().wecom_member_allowlist == {"Member_1", "member_2"}


def test_send_uses_tencent_paths_caches_token_and_enables_provider_dedup(transport):
    replies, requests = transport
    replies.extend([(200, TOKEN), (200, {"errcode": 0}), (200, {"errcode": 0})])
    sender = wecom.WecomSender()
    settings = configuration()
    sender.send(settings, "Member_1", "反馈 #41 状态更新", DETAIL)
    sender.send(settings, "Member_1", "反馈 #41 状态更新", DETAIL)

    (method, target), _ = requests[0]
    assert method == "GET"
    assert urlsplit(target).path == "/cgi-bin/gettoken"
    assert parse_qs(urlsplit(target).query) == {
        "corpid": [CONFIGURATION["wecom_corp_id"]],
        "corpsecret": [CONFIGURATION["wecom_agent_secret"]],
    }
    (method, target), options = requests[1]
    assert method == "POST"
    assert urlsplit(target).path == "/cgi-bin/message/send"
    assert parse_qs(urlsplit(target).query) == {"access_token": [TOKEN["access_token"]]}
    assert requests[1] == requests[2]
    assert json.loads(options["body"]) == {
        "touser": "Member_1",
        "agentid": 1000002,
        "msgtype": "textcard",
        "textcard": {
            "title": "迭程 IterFlow",
            "description": "反馈 #41 状态更新",
            "url": DETAIL,
            "btntxt": "详情",
        },
        "enable_duplicate_check": 1,
        "duplicate_check_interval": 1800,
    }


@pytest.mark.parametrize(
    ("reply", "status", "error_code"),
    [
        (
            (200, {"errcode": 0, "invaliduser": "private-member"}),
            "FAILED",
            "WECOM_RECIPIENT_REFUSED",
        ),
        (
            (200, {"errcode": 0, "unlicenseduser": "private-member"}),
            "FAILED",
            "WECOM_RECIPIENT_REFUSED",
        ),
        (
            (200, {"errcode": 81013, "errmsg": "private-member"}),
            "FAILED",
            "WECOM_RECIPIENT_REFUSED",
        ),
        ((200, {"errcode": 45009}), "RETRY", "WECOM_RATE_LIMITED"),
        ((429, {}), "RETRY", "WECOM_RATE_LIMITED"),
        ((403, {}), "FAILED", "WECOM_HTTP_REJECTED"),
        ((302, {}), "UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN"),
        ((503, {}), "UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN"),
        ((200, {"errcode": False}), "UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN"),
        ((200, {"errcode": 0, "invaliduser": []}), "UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN"),
        ((200, TimeoutError("private token in response")), "UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN"),
        (TimeoutError("private token in error"), "RETRY", "WECOM_CONNECTION_ERROR"),
    ],
)
def test_send_classifies_safe_provider_outcomes(transport, reply, status, error_code):
    replies, requests = transport
    replies.extend([(200, TOKEN), reply])
    with pytest.raises(wecom.WecomDeliveryError) as error:
        wecom.WecomSender().send(configuration(), "Member_1", "Test description", DETAIL)
    assert error.value.status == status
    assert str(error.value) == error_code
    assert len(requests) <= 2
    assert not replies


def test_invalid_token_is_refetched_before_the_next_attempt(transport):
    replies, requests = transport
    replies.extend(
        [
            (200, TOKEN),
            (200, {"errcode": 42001}),
            (200, TOKEN | {"access_token": "replacement"}),
            (200, {"errcode": 0}),
        ]
    )
    sender = wecom.WecomSender()
    settings = configuration()
    with pytest.raises(wecom.WecomDeliveryError, match="WECOM_PROVIDER_UNAVAILABLE") as error:
        sender.send(settings, "Member_1", "Test description", DETAIL)
    assert error.value.status == "RETRY"
    sender.send(settings, "Member_1", "Test description", DETAIL)
    assert [args[0] for args, _ in requests] == ["GET", "POST", "GET", "POST"]
    assert parse_qs(urlsplit(requests[-1][0][1]).query) == {"access_token": ["replacement"]}


def test_token_failure_does_not_attempt_to_send_or_expose_provider_response(transport):
    replies, requests = transport
    replies.append((200, {"errcode": 40001, "errmsg": "private token response"}))
    with pytest.raises(wecom.WecomDeliveryError, match=r"^WECOM_TOKEN_REJECTED$") as error:
        wecom.WecomSender().send(configuration(), "Member_1", "Test description", DETAIL)
    assert error.value.status == "FAILED"
    assert [args[0] for args, _ in requests] == ["GET"]


@pytest.mark.parametrize("member", ["@all", "member_1|member_2", "", "x" * 65])
def test_no_network_for_invalid_single_member(transport, member):
    with pytest.raises(wecom.WecomDeliveryError, match="WECOM_INVALID_PAYLOAD"):
        wecom.WecomSender().send(configuration(), member, "Test description", DETAIL)
    assert not transport[1]
