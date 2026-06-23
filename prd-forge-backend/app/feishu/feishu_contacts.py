"""飞书联系人搜索服务（OpenAPI 直连）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.feishu import openapi

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    ok: bool
    data: dict
    error_message: str | None = None


async def search_contacts(query: str, limit: int = 20, *, user_access_token: str | None = None) -> SearchResult:
    """按姓名搜索飞书联系人，返回 open_id + 姓名。"""
    try:
        users = await openapi.search_users(query, page_size=limit, user_access_token=user_access_token)
        return SearchResult(ok=True, data={"users": users})
    except Exception as exc:
        msg = str(exc)
        # 无 user token 时飞书 API 会返回 400（应用身份无通讯录权限）→ 给用户友好提示
        if not user_access_token:
            msg = "需要重新授权飞书。请刷新页面后重新点击分享 → 授权飞书。"
        logger.warning("搜索飞书联系人失败 (has_user_token=%s): %s", bool(user_access_token), str(exc))
        return SearchResult(ok=False, data={}, error_message=msg)
