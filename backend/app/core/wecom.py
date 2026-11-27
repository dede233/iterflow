"""Tencent WeCom application messages for a single bound member."""

import json
import ssl
from http.client import HTTPException, HTTPSConnection
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.parse import urlencode

from pydantic import SecretStr

from app.core.config import Settings, valid_wecom_member_user_id

WECOM_HOST = "qyapi.weixin.qq.com"
_MAX_RESPONSE_BYTES = 16_384
_TOKEN_REJECTED = {40014, 42001}
_RATE_LIMITED = {45009, 45011}


class WecomDeliveryError(Exception):
    def __init__(self, status: Literal["RETRY", "FAILED", "UNCERTAIN"], code: str):
        self.status = status
        self.code = code
        super().__init__(code)


def _request(path: str, payload: dict[str, object] | None = None) -> dict:
    connection = HTTPSConnection(WECOM_HOST, 443, timeout=5, context=ssl.create_default_context())
    is_send = payload is not None
    try:
        try:
            connection.connect()
        except ssl.SSLCertVerificationError:
            raise WecomDeliveryError("FAILED", "WECOM_TLS_INVALID") from None
        except (OSError, HTTPException):
            raise WecomDeliveryError("RETRY", "WECOM_CONNECTION_ERROR") from None

        try:
            if is_send:
                connection.request(
                    "POST",
                    path,
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            else:
                connection.request("GET", path)
            with connection.getresponse() as response:
                status = response.status
                if status == 200:
                    raw = response.read(_MAX_RESPONSE_BYTES + 1)
                    if len(raw) <= _MAX_RESPONSE_BYTES:
                        data = json.loads(raw)
                        if isinstance(data, dict) and type(data.get("errcode")) is int:
                            return data
                elif status == 429:
                    raise WecomDeliveryError("RETRY", "WECOM_RATE_LIMITED")
                elif 400 <= status < 500 and status != 408:
                    raise WecomDeliveryError("FAILED", "WECOM_HTTP_REJECTED")
        except (OSError, HTTPException, ValueError, RecursionError):
            # Request targets carry credentials, and responses can contain member UserIDs.
            pass
        if is_send:
            raise WecomDeliveryError("UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN")
        raise WecomDeliveryError("RETRY", "WECOM_TOKEN_UNAVAILABLE")
    finally:
        connection.close()


def _raise_provider_error(code: int, *, token_request: bool = False) -> None:
    if code == 0:
        return
    if code in _RATE_LIMITED:
        raise WecomDeliveryError("RETRY", "WECOM_RATE_LIMITED")
    if code == -1 or code in _TOKEN_REJECTED:
        raise WecomDeliveryError("RETRY", "WECOM_PROVIDER_UNAVAILABLE")
    if token_request:
        raise WecomDeliveryError("FAILED", "WECOM_TOKEN_REJECTED")
    if code in {60111, 81013}:
        raise WecomDeliveryError("FAILED", "WECOM_RECIPIENT_REFUSED")
    raise WecomDeliveryError("FAILED", "WECOM_MESSAGE_REJECTED")


class WecomSender:
    def __init__(self) -> None:
        self._token_lock = Lock()
        self._token: str | None = None
        self._expires_at = 0.0
        self._identity: tuple[str, int, SecretStr] | None = None

    def _access_token(self, settings: Settings) -> str:
        secret = settings.wecom_agent_secret
        if not secret:
            raise WecomDeliveryError("FAILED", "WECOM_TOKEN_REJECTED")
        identity = (settings.wecom_corp_id, settings.wecom_agent_id, secret)
        with self._token_lock:
            now = monotonic()
            if self._identity == identity and self._token and now < self._expires_at:
                return self._token
            query = urlencode(
                {"corpid": settings.wecom_corp_id, "corpsecret": secret.get_secret_value()}
            )
            data = _request(f"/cgi-bin/gettoken?{query}")
            _raise_provider_error(data["errcode"], token_request=True)
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise WecomDeliveryError("RETRY", "WECOM_TOKEN_UNAVAILABLE")
            expires_in = data.get("expires_in")
            self._expires_at = now + min(expires_in, 7200) - 60 if type(expires_in) is int else now
            self._token = token
            self._identity = identity
            return token

    def send(self, settings: Settings, member: str, description: str, url: str) -> None:
        if (
            not valid_wecom_member_user_id(member)
            or not 0 < len(description.encode("utf-8")) <= 512
            or not 0 < len(url.encode("utf-8")) <= 2048
        ):
            raise WecomDeliveryError("FAILED", "WECOM_INVALID_PAYLOAD")
        token = self._access_token(settings)
        query = urlencode({"access_token": token})
        data = _request(
            f"/cgi-bin/message/send?{query}",
            {
                "touser": member,
                "agentid": settings.wecom_agent_id,
                "msgtype": "textcard",
                "textcard": {
                    "title": "迭程 IterFlow",
                    "description": description,
                    "url": url,
                    "btntxt": "详情",
                },
                "enable_duplicate_check": 1,
                "duplicate_check_interval": 1800,
            },
        )
        code = data["errcode"]
        if code in _TOKEN_REJECTED:
            with self._token_lock:
                if self._token == token:
                    self._expires_at = 0
        _raise_provider_error(code)
        rejected = (data.get("invaliduser"), data.get("unlicenseduser"))
        if any(value is not None and not isinstance(value, str) for value in rejected):
            raise WecomDeliveryError("UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN")
        if any(rejected):
            raise WecomDeliveryError("FAILED", "WECOM_RECIPIENT_REFUSED")


send_wecom = WecomSender().send
