"""解析器公共：超长截断 + ai_inferred 标注。"""

from __future__ import annotations

from app.config import get_settings

_AI_INFERRED_MARKER = "<ai_inferred>文件过长，已截断</ai_inferred>"


def truncate_with_marker(text: str, filename: str) -> str:
    """若文本超过 `MAX_FILE_CHARS`，在尾部追加 ai_inferred 标注并截断。

    Args:
        text: 原始文本。
        filename: 仅用于日志 / 调试。

    Returns:
        截断后文本（≤ MAX_FILE_CHARS + 标注长度）。
    """
    limit = get_settings().max_file_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "\n" + _AI_INFERRED_MARKER
