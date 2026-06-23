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


async def search_contacts(query: str, limit: int = 20) -> SearchResult:
    """按姓名搜索飞书联系人，返回 open_id + 姓名。"""
    try:
        users = await openapi.search_users(query, page_size=limit)
        return SearchResult(ok=True, data={"users": users})
    except Exception as exc:
        msg = str(exc)
        logger.warning("搜索飞书联系人失败: %s", msg)
        return SearchResult(ok=False, data={}, error_message=msg)
