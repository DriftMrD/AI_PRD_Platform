"""飞书 OpenAPI 直连：搜索用户、上传文件、发送消息。
替代 lark-cli，直接通过飞书服务端 OpenAPI 调用，适用于 Render 等云端环境。

支持两种 token 模式：
- tenant_access_token（应用身份）：仅能拿到 open_id
- user_access_token（用户身份）：能拿到姓名、邮箱、部门等完整信息
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

import httpx

from app.config import get_settings
from app.feishu.jssdk import _tenant_access_token

logger = logging.getLogger(__name__)
_FEISHU_API = "https://open.feishu.cn/open-apis"


async def _get_token(user_access_token: str | None = None) -> str:
    """获取 token：优先用 user_access_token，否则用 tenant_access_token。"""
    if user_access_token:
        return user_access_token
    settings = get_settings()
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法调用飞书 API")
    return await _tenant_access_token(settings.feishu_app_id, settings.feishu_app_secret)


async def _feishu_get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    user_access_token: str | None = None,
) -> dict:
    """带 token 的飞书 GET。"""
    token = await _get_token(user_access_token)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_FEISHU_API}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 API 错误 [{path}]: {data.get('msg', data)}")
    return data


async def _feishu_post(
    path: str,
    body: dict | None = None,
    files: dict | None = None,
    *,
    user_access_token: str | None = None,
) -> dict:
    """带 token 的飞书 POST（JSON 或 multipart）。"""
    token = await _get_token(user_access_token)
    async with httpx.AsyncClient(timeout=30.0) as client:
        if files:
            resp = await client.post(
                f"{_FEISHU_API}{path}",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )
        else:
            resp = await client.post(
                f"{_FEISHU_API}{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=body,
            )
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 API 错误 [{path}]: {data.get('msg', data)}")
    return data


async def search_users(
    query: str,
    page_size: int = 20,
    *,
    user_access_token: str | None = None,
) -> list[dict]:
    """按姓名搜索飞书用户（必须用 user_access_token，走 /search/v1/user）。"""
    if not user_access_token:
        raise RuntimeError("搜索联系人需要飞书用户授权")

    data = await _feishu_get(
        "/search/v1/user",
        params={"query": query, "page_size": page_size},
        user_access_token=user_access_token,
    )
    items = data.get("data", {}).get("users", [])
    results: list[dict] = []
    for item in items:
        oid = item.get("open_id", "")
        name = item.get("name", "")
        email = item.get("email", "")
        dept_ids: list[str] = item.get("department_ids", []) or []

        # fallback: 逐个查用户详情
        if not name and oid:
            try:
                detail = await _feishu_get(
                    f"/contact/v3/users/{oid}",
                    params={"user_id_type": "open_id"},
                    user_access_token=user_access_token,
                )
                user = detail.get("data", {}).get("user", {})
                name = user.get("name", "")
                email = email or user.get("email", "")
                dept_ids = dept_ids or user.get("department_ids", []) or []
            except Exception:
                pass

        # 仍无姓名 → 用 open_id 片段展示
        if not name:
            name = f"用户 {oid[:12]}…" if len(oid) > 12 else f"用户 {oid}"

        department = await _resolve_dept_path(dept_ids, user_access_token=user_access_token) if dept_ids else ""
        results.append({
            "open_id": oid,
            "name": name,
            "email": email,
            "department": department,
        })
    return results


async def _resolve_dept_path(
    dept_ids: list[str],
    *,
    user_access_token: str | None = None,
) -> str:
    """将部门 ID 列表解析为可读路径（取第一个）。"""
    if not dept_ids:
        return ""
    try:
        data = await _feishu_get(
            f"/contact/v3/departments/{dept_ids[0]}",
            user_access_token=user_access_token,
        )
        dept = data.get("data", {}).get("department", {})
        return dept.get("name", "")
    except Exception:
        return ""


async def upload_file(content: str, filename: str, file_type: str = "stream") -> dict[str, Any]:
    """上传文件到飞书 IM，返回 file_key 等。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name

    try:
        file_size = os.path.getsize(tmp_path)
        with open(tmp_path, "rb") as fh:
            data = await _feishu_post(
                "/im/v1/files",
                files={
                    "file_type": (None, file_type),
                    "file_name": (None, filename),
                    "file": (filename, fh, "application/octet-stream"),
                },
            )
        return data.get("data", {})
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def send_file_message(
    receive_id: str,
    file_key: str,
    msg_type: str = "file",
) -> dict:
    """发送文件消息给指定用户。"""
    return await _feishu_post(
        "/im/v1/messages",
        params={"receive_id_type": "open_id"},
        body={
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": f'{{"file_key":"{file_key}"}}',
        },
    )
