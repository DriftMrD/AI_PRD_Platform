"""LLM 适配器子包。"""

from app.llm.base import BaseLLMAdapter
from app.llm.factory import get_adapter

__all__ = ["BaseLLMAdapter", "get_adapter"]
