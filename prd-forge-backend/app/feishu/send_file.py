"""飞书发送 MD 文件服务（OpenAPI 直连）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.feishu import openapi

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    ok: bool
    data: dict
    error_message: str | None = None


async def send_md_file_to_user(
    user_open_id: str,
    content: str,
    title: str,
    version_label: str | None = None,
    *,
    user_access_token: str | None = None,
) -> SendResult:
    """将 MD 内容作为文件发送给指定飞书用户（OpenAPI）。"""
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-()（）")
    if not safe_title.strip():
        safe_title = "PRD"
    filename = f"{safe_title}_{version_label}.md" if version_label else f"{safe_title}.md"

    try:
        # 1. 上传文件到飞书 IM
        file_info = await openapi.upload_file(content, filename)
        file_key = file_info.get("file_key")
        if not file_key:
            return SendResult(ok=False, data={}, error_message="飞书文件上传失败：未返回 file_key")

        # 2. 发送文件消息
        msg_info = await openapi.send_file_message(user_open_id, file_key)
        return SendResult(ok=True, data={"message_id": msg_info.get("data", {}).get("message_id", "")})
    except Exception as exc:
        msg = str(exc)
        logger.warning("飞书发送文件失败: %s", msg)
        return SendResult(ok=False, data={}, error_message=msg)
