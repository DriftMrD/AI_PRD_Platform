"""飞书分享内容临时存储（跨浏览器/飞书 WebView 无法用 localStorage 互通）。"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

_TTL_SECONDS = 600
_MAX_ENTRIES = 200


@dataclass
class SharePayload:
    text: str
    title: str
    expires_at: float


_store: dict[str, SharePayload] = {}


def _purge_expired() -> None:
    now = time.time()
    expired = [k for k, v in _store.items() if v.expires_at <= now]
    for key in expired:
        _store.pop(key, None)
    if len(_store) > _MAX_ENTRIES:
        oldest = sorted(_store.items(), key=lambda item: item[1].expires_at)
        for key, _ in oldest[: len(_store) - _MAX_ENTRIES]:
            _store.pop(key, None)


def create(text: str, title: str) -> str:
    _purge_expired()
    share_id = secrets.token_urlsafe(12)
    _store[share_id] = SharePayload(
        text=text,
        title=title,
        expires_at=time.time() + _TTL_SECONDS,
    )
    return share_id


def consume(share_id: str) -> SharePayload | None:
    _purge_expired()
    payload = _store.pop(share_id, None)
    if payload is None or time.time() > payload.expires_at:
        return None
    return payload
