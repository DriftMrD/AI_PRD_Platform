"""文件解析器子包。"""

from app.parsers.base import FileParser
from app.parsers.factory import get_parser

__all__ = ["FileParser", "get_parser"]
