"""飞书联系人搜索服务。"""

from __future__ import annotations

import logging

from app.feishu.cli import CliResult, run_lark

logger = logging.getLogger(__name__)


async def search_contacts(query: str, limit: int = 20) -> CliResult:
    """按姓名搜索飞书联系人，返回 open_id + 姓名。"""
    result = run_lark(
        ["contact", "+search-user", "--query", query, "--as", "user"],
        timeout=15,
    )
    if not result.ok:
        return result

    data = result.data.get("data", {})
    users = data.get("users", [])
    # 精简字段，只返回前端需要的
    simplified = []
    for u in users[:limit]:
        simplified.append({
            "open_id": u.get("open_id", ""),
            "name": u.get("localized_name", ""),
            "email": u.get("email", ""),
            "department": u.get("department", ""),
        })

    return CliResult(ok=True, data={"users": simplified})
