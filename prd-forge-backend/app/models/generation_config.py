"""LLM 生成参数（model / temperature / max_tokens）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """单次 LLM 调用的生成参数。"""

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
