"""飞书发送 MD 文件服务。"""

from __future__ import annotations

import logging
import os
import shutil

from app.feishu.cli import CliResult, make_temp_md_file, run_lark

logger = logging.getLogger(__name__)


async def send_md_file_to_user(
    user_open_id: str,
    content: str,
    title: str,
    version_label: str | None = None,
) -> CliResult:
    """将 MD 内容作为文件发送给指定飞书用户。"""
    # 生成安全的文件名
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-()（）")
    if not safe_title.strip():
        safe_title = "PRD"
    if version_label:
        filename = f"{safe_title}_{version_label}.md"
    else:
        filename = f"{safe_title}.md"

    tmpdir, fname = make_temp_md_file(content, filename)

    try:
        # 从临时目录执行，因为 lark-cli --file 需要相对路径
        result = run_lark(
            [
                "im", "+messages-send",
                "--user-id", user_open_id,
                "--file", f"./{fname}",
                "--as", "user",
            ],
            cwd=tmpdir,
            timeout=30,
        )
        return result
    finally:
        # 清理临时文件
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
