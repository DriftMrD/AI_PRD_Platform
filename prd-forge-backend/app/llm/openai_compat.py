"""OpenAI 兼容 `/chat/completions` 流式适配器（基于 httpx.AsyncClient）。"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings
from app.errors import AppError, LLM_AUTH, LLM_TIMEOUT, LLM_UPSTREAM
from app.llm.base import BaseLLMAdapter
from app.prompts.skill_loader import get_generation_config


class OpenAICompatAdapter(BaseLLMAdapter):
    """OpenAI 兼容协议（`/chat/completions`，`stream: true`）。

    - 首 token 超时：`LLM_FIRST_TOKEN_TIMEOUT_S`（仅在首个 chunk 到达前生效）
    - 总超时：`LLM_TIMEOUT_S`（read timeout）
    - HTTP 401/403 → `LLM_AUTH`；5xx → `LLM_UPSTREAM`
    - 网络 / 超时 → `LLM_TIMEOUT`
    """

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        # 工厂可以注入一个共享 client；未注入则自建（每实例）
        self._owns_client = client is None
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.llm_timeout_s,
                write=10.0,
                pool=10.0,
            )
        )
        self._url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        """流式调用 LLM，按 chunk yield 增量文本。

        Raises:
            AppError(LLM_AUTH / LLM_TIMEOUT / LLM_UPSTREAM)
        """
        generation = get_generation_config()
        payload: dict[str, Any] = {
            "model": generation.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if generation.temperature is not None:
            payload["temperature"] = generation.temperature
        if generation.max_tokens is not None:
            payload["max_tokens"] = generation.max_tokens

        try:
            async with self._client.stream(
                "POST",
                self._url,
                headers=self._headers,
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ) as response:
                # HTTP 状态码在 __aenter__ 后确定
                if response.status_code in (401, 403):
                    raise AppError(
                        LLM_AUTH,
                        f"LLM 鉴权失败（HTTP {response.status_code}）",
                        retriable=False,
                    )
                if 500 <= response.status_code < 600:
                    raise AppError(
                        LLM_UPSTREAM,
                        f"LLM 上游错误（HTTP {response.status_code}）",
                        retriable=True,
                    )
                if response.status_code >= 400:
                    # 4xx 其他情况：归到上游错误（不暴露鉴权细节）
                    body = await response.aread()
                    raise AppError(
                        LLM_UPSTREAM,
                        f"LLM 调用失败（HTTP {response.status_code}）：{body[:200]!r}",
                        retriable=False,
                    )

                first_token_deadline = time.monotonic() + self._settings.llm_first_token_timeout_s
                got_first = False

                async for line in response.aiter_lines():
                    if not got_first:
                        # 首 token 超时检查
                        if time.monotonic() > first_token_deadline:
                            raise AppError(
                                LLM_TIMEOUT,
                                f"LLM 首 token 超时（>{self._settings.llm_first_token_timeout_s}s）",
                                retriable=True,
                            )

                    if not line:
                        continue
                    # SSE 帧以 "data: " 起；OpenAI 用 "[DONE]" 终止
                    if line.startswith("data:"):
                        data = line[len("data:"):].strip()
                    else:
                        data = line.strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue

                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        # 忽略无法解析的行，避免单点坏数据阻断流
                        continue

                    delta = self._extract_delta(obj)
                    if delta:
                        got_first = True
                        yield delta
        except httpx.TimeoutException as exc:
            raise AppError(
                LLM_TIMEOUT,
                f"LLM 调用超时：{exc}",
                retriable=True,
            ) from exc
        except httpx.HTTPError as exc:
            # 网络层错误
            raise AppError(
                LLM_UPSTREAM,
                f"LLM 网络错误：{exc}",
                retriable=True,
            ) from exc

    @staticmethod
    def _extract_delta(obj: dict[str, Any]) -> str:
        """从 OpenAI 兼容 chunk 中提取增量文本。"""
        try:
            choices = obj.get("choices") or []
            if not choices:
                return ""
            choice = choices[0]
            # 兼容：delta.content / text / message.content
            delta = choice.get("delta") or choice.get("message") or {}
            content = delta.get("content")
            if content is None and "text" in delta:
                content = delta["text"]
            return content or ""
        except (AttributeError, TypeError, KeyError):
            return ""

    async def aclose(self) -> None:
        """关闭自身拥有的 httpx client。"""
        if self._owns_client:
            await self._client.aclose()
