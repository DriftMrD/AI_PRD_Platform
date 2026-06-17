"""`FileParser` 抽象接口（Protocol 风格，便于鸭子类型）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FileParser(Protocol):
    """文件解析器协议。

    实现需在 `parse` 中：
    1. 接受原始字节 `content` 与 `filename`。
    2. 返回纯文本（已包含必要截断标注）。
    3. 解析失败抛 `AppError(FILE_PARSE_FAILED, ...)`。
    """

    def parse(self, content: bytes, filename: str) -> str:
        """解析文件为文本。

        Args:
            content: 原始字节。
            filename: 原始文件名（用于日志 / 类型推断回退）。

        Returns:
            解析后的纯文本（可能含 `<ai_inferred>...</ai_inferred>` 截断标注）。
        """
        ...
