"""飞书 H5 JSAPI 鉴权：tenant_access_token + jsapi_ticket 签名。"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

import httpx

_FEISHU_API = "https://open.feishu.cn/open-apis"


@dataclass
class _TokenCache:
    value: str
    expires_at: float


@dataclass
class _TicketCache:
    value: str
    expires_at: float


_token_cache: _TokenCache | None = None
_ticket_cache: _TicketCache | None = None


def _is_valid(cache: _TokenCache | _TicketCache | None) -> bool:
    return cache is not None and time.time() < cache.expires_at - 60


async def _tenant_access_token(app_id: str, app_secret: str) -> str:
    global _token_cache
    if _is_valid(_token_cache):
        return _token_cache.value  # type: ignore[union-attr]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_FEISHU_API}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 tenant_access_token 失败: {data.get('msg', data)}")

    token = str(data["tenant_access_token"])
    expire_in = int(data.get("expire", 7200))
    _token_cache = _TokenCache(value=token, expires_at=time.time() + expire_in)
    return token


async def _jsapi_ticket(app_id: str, app_secret: str) -> str:
    global _ticket_cache
    if _is_valid(_ticket_cache):
        return _ticket_cache.value  # type: ignore[union-attr]

    token = await _tenant_access_token(app_id, app_secret)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_FEISHU_API}/jssdk/ticket/get",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 jsapi_ticket 失败: {data.get('msg', data)}")

    ticket = str(data["data"]["ticket"])
    expire_in = int(data["data"].get("expire_in", 7200))
    _ticket_cache = _TicketCache(value=ticket, expires_at=time.time() + expire_in)
    return ticket


def _sign(ticket: str, nonce: str, timestamp: int, url: str) -> str:
    verify_str = (
        f"jsapi_ticket={ticket}&noncestr={nonce}&timestamp={timestamp}&url={url}"
    )
    return hashlib.sha1(verify_str.encode("utf-8")).hexdigest()


async def build_jssdk_config(app_id: str, app_secret: str, url: str) -> dict[str, object]:
    """生成前端 h5sdk.config 所需参数。"""
    ticket = await _jsapi_ticket(app_id, app_secret)
    nonce = secrets.token_hex(8)
    timestamp = int(time.time() * 1000)
    signature = _sign(ticket, nonce, timestamp, url)
    return {
        "enabled": True,
        "appId": app_id,
        "timestamp": timestamp,
        "nonceStr": nonce,
        "signature": signature,
    }
