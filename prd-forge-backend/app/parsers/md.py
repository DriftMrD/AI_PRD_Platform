"""Markdown 解析器（按纯文本处理，UTF-8 解码即可）。"""

from __future__ import annotations

from app.parsers._truncate import truncate_with_marker


class MdParser:
    """`.md` 解析：直接 UTF-8 解码，超长截断。"""

    def parse(self, content: bytes, filename: str) -> str:
        text = content.decode("utf-8", errors="replace")
        return truncate_with_marker(text, filename)
