"""LLM 适配器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLMAdapter(ABC):
    """所有 LLM 适配器的统一接口。

    实现需以 `async for` 形式逐 token / 逐片段 yield 增量文本。
    失败抛 `AppError`，由路由层捕获后转 SSE error。
    """

    @abstractmethod
    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        """流式调用 LLM。

        Args:
            system: system 消息。
            user: user 消息。

        Yields:
            增量文本片段。
        """
        raise NotImplementedError
        yield  # pragma: no cover  # 让该方法成为生成器

    async def aclose(self) -> None:
        """释放底层资源（默认 no-op；子类可覆写）。"""
        return None
