"""飞书 OAuth 2.0 用户授权：获取 user_access_token，用于以用户身份调用 API。

通过用户身份调 API 可拿到联系人姓名、邮箱、部门等字段（应用身份只能拿 open_id）。
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

import httpx
from fastapi import Cookie, HTTPException, Request

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, dict] = {}  # open_id → {token, expires_at, refresh_token}

# cookie 名
FEISHU_USER_TOKEN_COOKIE = "feishu_user_token"

# 飞书 OAuth API
_AUTH_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_URL = f"{_AUTH_BASE}/authen/v1/oidc/access_token"
_USER_INFO_URL = f"{_AUTH_BASE}/authen/v1/user_info"


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
    qs = "&".join(f"{k}={httpx.URL('')._encode_param(v)}" for k, v in params.items())
    return f"{_AUTH_BASE}/authen/v1/authorize?{qs}"


async def exchange_code(code: str) -> dict[str, Any]:
    """用授权码换取 user_access_token。

    Returns:
        {"access_token": str, "refresh_token": str, "expires_in": int, "open_id": str, "name": str}
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "grant_type": "authorization_code",
                "code": code,
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
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


def store_token(open_id: str, token_data: dict) -> None:
    """缓存 user_access_token。"""
    _TOKEN_CACHE[open_id] = {
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + token_data.get("expires_in", 7200) - 60,
        "name": token_data.get("name", ""),
    }


async def get_valid_user_token(open_id: str) -> str | None:
    """获取有效的 user_access_token，过期则刷新。"""
    entry = _TOKEN_CACHE.get(open_id)
    if not entry:
        return None

    if time.time() < entry["expires_at"]:
        return entry["access_token"]

    # token 过期，尝试刷新
    refreshed = await _refresh_token(entry["refresh_token"])
    if refreshed:
        store_token(open_id, refreshed)
        return refreshed.get("access_token")

    # 刷新失败，删除过期缓存
    _TOKEN_CACHE.pop(open_id, None)
    return None


def extract_user_token_from_request(request: Request) -> str | None:
    """从请求中提取有效的 user_access_token。

    优先从 Cookie 读取 open_id → 查缓存 → 返回 token。
    """
    open_id = request.cookies.get("feishu_user_open_id")
    if not open_id:
        return None
    return _TOKEN_CACHE.get(open_id, {}).get("access_token")


def read_token_from_cookie(open_id: str | None = Cookie(default=None, alias="feishu_user_open_id")) -> str | None:
    """FastAPI 依赖：从 Cookie 读取 user_access_token（仅返回，不校验过期）。"""
    if not open_id:
        return None
    return _TOKEN_CACHE.get(open_id, {}).get("access_token")
