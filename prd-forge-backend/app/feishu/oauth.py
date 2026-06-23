"""飞书 OAuth 2.0 用户授权：获取 user_access_token，用于以用户身份调用 API。

Token 存储策略：
- 内存缓存 _TOKEN_CACHE（快速路径，Render 休眠后会丢失）
- httpOnly Cookie（持久化路径，Render 重启后仍可用）

通过用户身份调 API 可拿到联系人姓名、邮箱、部门等字段（应用身份只能拿 open_id）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json as _json
import logging
import secrets
import time
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Cookie, Request

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, dict] = {}  # open_id → {token, expires_at, refresh_token}（内存加速）

# Cookie 名（存 token 本身，不依赖内存缓存）
COOKIE_ACCESS_TOKEN = "feishu_at"
COOKIE_REFRESH_TOKEN = "feishu_rt"
COOKIE_OPEN_ID = "feishu_oid"

# Session token 机制：绕过浏览器跨站 Cookie 拦截（ITP）
# OAuth 回调后生成 HMAC 签名的自包含 session token，前端存 sessionStorage 并通过 API body 回传。
# token 数据直接嵌入 session token 中，Render 重启不丢（不再依赖内存 _SESSION_STORE）。
_SESSION_STORE: dict[str, dict] = {}  # session_token → {access_token, refresh_token, expires_at}（已废弃，保留兼容）

# 飞书 OAuth API
_AUTH_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_URL = f"{_AUTH_BASE}/authen/v1/oidc/access_token"
_USER_INFO_URL = f"{_AUTH_BASE}/authen/v1/user_info"

# Cookie 基础参数（跨站可携带，https 强制）
_COOKIE_BASE = {"httponly": True, "secure": True, "samesite": "none"}


def _get_redirect_uri() -> str:
    """从配置读取 OAuth 回调地址，未配置时用默认 Render 地址。"""
    settings = get_settings()
    if settings.feishu_oauth_redirect_uri:
        return settings.feishu_oauth_redirect_uri
    # 默认：Render 部署地址
    return "https://prd-forge-backend.onrender.com/api/feishu/oauth/callback"


def build_authorize_url(state: str | None = None) -> str:
    """构建飞书 OAuth 授权页 URL。

    Args:
        state: 可选 state 参数（用于防 CSRF + 记录回调后跳转目标）
    """
    settings = get_settings()
    if not settings.feishu_app_id:
        raise RuntimeError("未配置 FEISHU_APP_ID，无法构建授权 URL")

    if state is None:
        state = secrets.token_urlsafe(16)

    redirect_uri = _get_redirect_uri()
    params = {
        "app_id": settings.feishu_app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "contact:user.base:readonly",  # 获取用户基本信息（姓名、邮箱等）
    }
    qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"{_AUTH_BASE}/authen/v1/authorize?{qs}"


async def _get_app_access_token() -> str:
    """获取 app_access_token（用于 OIDC token 交换、user_info 等应用级操作）。"""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_AUTH_BASE}/auth/v3/app_access_token/internal",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 app_access_token 失败: {data.get('msg', data)}")
    return str(data["app_access_token"])


async def exchange_code(code: str) -> dict[str, Any]:
    """用授权码换取 user_access_token。

    飞书 OIDC 2.0 需要 app_access_token 做 Bearer 认证，
    不能直接在 body 里传 app_id/app_secret。

    Returns:
        {"access_token": str, "refresh_token": str, "expires_in": int, "open_id": str, "name": str}
    """
    app_token = await _get_app_access_token()
    redirect_uri = _get_redirect_uri()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            headers={
                "Authorization": f"Bearer {app_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 OAuth 换 token 失败: {data.get('msg', data)}")
    return data.get("data", {})


async def _refresh_token(refresh_token: str) -> dict[str, Any] | None:
    """刷新过期的 user_access_token。"""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                headers={"Content-Type": "application/json; charset=utf-8"},
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "app_id": settings.feishu_app_id,
                    "app_secret": settings.feishu_app_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("刷新飞书 token 失败: %s", data.get("msg"))
                return None
        return data.get("data", {})
    except Exception as e:
        logger.warning("刷新飞书 token 异常: %s", e)
        return None


# ---- Session Token（自包含，绕过跨站 Cookie + Render 重启） ----


def _signing_key() -> bytes:
    """派生 HMAC 签名密钥（基于 app_secret，不硬编码）。"""
    settings = get_settings()
    return hashlib.sha256(
        (settings.feishu_app_secret or "prd-forge-default").encode()
    ).digest()


_SESSION_VERSION = "v2"

def create_session(token_data: dict) -> str:
    """将 token 编码为 HMAC 签名的自包含 session token。

    数据直接嵌在 token 内（base64），不依赖内存存储，Render 重启不丢。
    格式：v2.base64(payload).hex_signature(32)
    """
    payload = _json.dumps({
        "at": token_data.get("access_token", ""),
        "rt": token_data.get("refresh_token", ""),
        "exp": int(time.time() + token_data.get("expires_in", 7200) - 60),
    }).encode()

    encoded = base64.urlsafe_b64encode(payload).decode()
    sig = hmac.new(_signing_key(), encoded.encode(), hashlib.sha256).hexdigest()[:32]
    session_token = f"{_SESSION_VERSION}.{encoded}.{sig}"

    # 同时写内存 store（兼容旧逻辑 + Render 热缓存加速）
    _SESSION_STORE[session_token] = {
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + token_data.get("expires_in", 7200) - 60,
    }
    return session_token


def get_token_by_session(session_token: str) -> str | None:
    """通过 session token 获取 access_token。

    优先查内存 store（快），miss 则从自包含 payload 解码（跨 Render 重启）。
    HMAC 签名验证防篡改。v2 版本带版本前缀，旧版 token 直接拒绝。
    """
    # 0. 版本检查：旧 token（无 v2. 前缀）直接拒绝
    if not session_token.startswith(f"{_SESSION_VERSION}."):
        logger.warning("飞书 session token 版本过旧（需重新授权），got: %s...", session_token[:20])
        return None

    # 1. 内存 store（Render 实例热时最快）
    entry = _SESSION_STORE.get(session_token)
    if entry and time.time() < entry["expires_at"]:
        return entry["access_token"]

    # 2. 自包含 payload（Render 重启后仍可用）
    try:
        # 格式：v2.encoded.sig
        _, encoded, sig = session_token.split(".", 2)

        # HMAC 签名验证
        expected_sig = hmac.new(_signing_key(), encoded.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            logger.warning("飞书 session token 签名验证失败（可能被篡改）")
            return None

        payload = base64.urlsafe_b64decode(encoded.encode())
        data = _json.loads(payload)
        if time.time() > data.get("exp", 0):
            return None  # 已过期

        at = data.get("at", "")
        if not at:
            return None

        # 回写内存（后续请求走快速路径）
        _SESSION_STORE[session_token] = {
            "access_token": at,
            "refresh_token": data.get("rt", ""),
            "expires_at": data.get("exp", 0),
        }
        return at
    except Exception:
        return None


# ---- Cookie 读写 ----

def _cookie_age(token_data: dict) -> int:
    """根据 token expires_in 计算 cookie max_age（秒），至少 3600。"""
    return max(3600, token_data.get("expires_in", 7200))


def _set_token_cookies(response: "RedirectResponse | JSONResponse", token_data: dict) -> None:
    """在 response 上同时写入 token cookies + 内存缓存。"""
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    open_id = token_data.get("open_id", "")
    if not access_token or not open_id:
        return

    age = _cookie_age(token_data)
    kwargs = {**_COOKIE_BASE, "max_age": age}

    if access_token:
        response.set_cookie(key=COOKIE_ACCESS_TOKEN, value=access_token, **kwargs)
    if refresh_token:
        response.set_cookie(key=COOKIE_REFRESH_TOKEN, value=refresh_token, **kwargs)
    if open_id:
        response.set_cookie(key=COOKIE_OPEN_ID, value=open_id, **kwargs)

    # 清理旧版 cookie（v1 用 feishu_user_open_id 存 open_id，现已改为 feishu_oid）
    response.delete_cookie(key="feishu_user_open_id", path="/", **{k: v for k, v in _COOKIE_BASE.items() if k != "max_age"})

    # 同时写内存缓存加速后续请求
    store_token(open_id, token_data)


def store_token(open_id: str, token_data: dict) -> None:
    """缓存 user_access_token 到内存（加速）。

    持久化 token 由 cookie 负责，此函数仅写入内存。
    """
    _TOKEN_CACHE[open_id] = {
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + token_data.get("expires_in", 7200) - 60,
        "name": token_data.get("name", ""),
    }


def extract_user_token_from_request(
    request: Request,
    session_token: str | None = None,
) -> str | None:
    """从请求中提取 user_access_token。

    优先级：session_token（前端传）→ Cookie（跨站可用时）→ 内存缓存。
    新增 session_token 机制：浏览器 ITP 会拦截跨站 Cookie，但 session_token
    由前端通过 API body 明文回传，完全绕开 Cookie 限制。
    """
    # 1. Session token（最高优先级，绕过跨站 Cookie 限制）
    if session_token:
        token = get_token_by_session(session_token)
        if token:
            return token

    # 2. Cookie 路径（用户已在 Render 同域授权时有效）
    open_id = request.cookies.get(COOKIE_OPEN_ID)
    if open_id:
        entry = _TOKEN_CACHE.get(open_id)
        if entry and time.time() < entry["expires_at"]:
            return entry["access_token"]

    access_token = request.cookies.get(COOKIE_ACCESS_TOKEN)
    if access_token and open_id:
        refresh_token = request.cookies.get(COOKIE_REFRESH_TOKEN) or ""
        _TOKEN_CACHE[open_id] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": time.time() + 3600,
        }
        return access_token

    return None
