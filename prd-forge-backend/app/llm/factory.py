"""LLM 适配器工厂：按 `LLM_PROVIDER` 返回对应实现。

工厂读取配置一次（启动期），不每请求重建 httpx.Client。
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.errors import AppError, INTERNAL
from app.llm.base import BaseLLMAdapter
from app.llm.openai_compat import OpenAICompatAdapter


@lru_cache(maxsize=1)
def get_adapter() -> BaseLLMAdapter:
    """获取（缓存）单例 LLM 适配器。

    Returns:
        与 `Settings.llm_provider` 对应的适配器实例。

    Raises:
        AppError(INTERNAL): 未知的 provider 字符串。
    """
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "openai":
        return OpenAICompatAdapter(settings)
    raise AppError(
        INTERNAL,
        f"Unknown LLM provider: {provider!r}",
        retriable=False,
    )


def reset_for_tests() -> None:
    """QA 阶段使用：清空工厂缓存。"""
    get_adapter.cache_clear()
