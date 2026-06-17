"""纯文本解析器。"""

from __future__ import annotations

from app.parsers._truncate import truncate_with_marker


class TxtParser:
    """`.txt` 解析：UTF-8 解码（容错）。"""

    def parse(self, content: bytes, filename: str) -> str:
        text = content.decode("utf-8", errors="replace")
        return truncate_with_marker(text, filename)
