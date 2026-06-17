"""按文件后缀分派解析器。

未知后缀抛 `FILE_PARSE_FAILED`；调用方负责捕获后转 SSE error。
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.errors import AppError, FILE_PARSE_FAILED
from app.parsers.base import FileParser
from app.parsers.docx import DocxParser
from app.parsers.md import MdParser
from app.parsers.pdf import PdfParser
from app.parsers.txt import TxtParser

_EXT_MAP: dict[str, FileParser] = {
    ".md": MdParser(),
    ".markdown": MdParser(),
    ".txt": TxtParser(),
    ".docx": DocxParser(),
    ".pdf": PdfParser(),
}


def get_parser(filename: str) -> FileParser:
    """根据文件名后缀返回对应解析器实例。

    Args:
        filename: 原始文件名（含后缀）。

    Returns:
        实现 `FileParser` 协议的对象。

    Raises:
        AppError(FILE_PARSE_FAILED): 未知 / 不支持的后缀。
    """
    suffix = PurePosixPath(filename).suffix.lower()
    parser = _EXT_MAP.get(suffix)
    if parser is None:
        raise AppError(
            FILE_PARSE_FAILED,
            f"不支持的文件类型：{suffix or '(无后缀)'}（{filename}）",
            retriable=False,
        )
    return parser


def supported_extensions() -> tuple[str, ...]:
    """返回所有支持的后缀（小写、含点）。"""
    return tuple(_EXT_MAP.keys())
