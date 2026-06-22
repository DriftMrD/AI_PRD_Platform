"""`POST /api/generate` 路由：multipart → 解析 → 构 prompt → LLM 流式 → SSE。

SSE 事件顺序：
  start → progress(parse) → progress(build_prompt) → 多次 chunk → done

每 chunk 前 `await request.is_disconnected()`；断开则 cancel LLM 流并
emit error(code=CLIENT_DISCONNECTED)。

所有错误统一抛 `AppError`，由 `app/main.py` 中注册的全局 handler 转 SSE。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, Form, Request, UploadFile  # noqa: F401  (File 注入)
from sse_starlette.event import ServerSentEvent
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.errors import (
    AppError,
    CLIENT_DISCONNECTED,
    FILE_TOO_LARGE,
    OK,
)
from app.llm.factory import get_adapter
from app.models.sse import (
    EVENT_CHUNK,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_PROGRESS,
    EVENT_START,
    ChunkEvent,
    DoneEvent,
    ErrorEvent,
    ProgressEvent,
    StartEvent,
)
from app.parsers.factory import get_parser, supported_extensions
from app.prompts import builder as prompt_builder
from app.prompts.skill_loader import get_generation_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(event: str, data: dict) -> ServerSentEvent:
    """构造一个 SSE 事件（data 为 JSON 字符串）。"""
    return ServerSentEvent(
        data=json.dumps(data, ensure_ascii=False),
        event=event,
    )


@router.post("/generate")
async def generate(
    request: Request,
    text: str = Form(default=""),
    template: str = Form(default="standard"),
    language: str = Form(default="zh"),
    detail: str = Form(default="standard"),
    role: str = Form(default=""),
    feature_name: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),  # noqa: B008  (FastAPI Form 注入)
) -> EventSourceResponse:
    """处理生成请求，返回 SSE 流。"""
    settings = get_settings()
    request_id = __generate_request_id()
    started_at = time.monotonic()
    log = logger.getChild(request_id)

    async def event_source() -> AsyncIterator[ServerSentEvent]:
        total_chars = 0
        stream_task: asyncio.Task[None] | None = None
        try:
            # 1) start
            yield _sse(EVENT_START, StartEvent(request_id=request_id, ts=time.time()).model_dump())

            # 2) progress: 解析
            yield _sse(
                EVENT_PROGRESS,
                ProgressEvent(stage="parse", percent=5, message="开始解析附件").model_dump(),
            )

            files_texts: list[str] = []
            max_bytes = settings.max_file_size_bytes
            for idx, f in enumerate(files or [], start=1):
                if not f.filename:
                    continue
                # 后缀白名单
                from pathlib import PurePosixPath

                suffix = PurePosixPath(f.filename).suffix.lower()
                if suffix not in supported_extensions():
                    raise AppError(
                        "INVALID_FILE_TYPE",
                        f"不支持的文件类型：{suffix or '(无后缀)'}（{f.filename}）",
                        retriable=False,
                    )
                content = await f.read()
                if len(content) > max_bytes:
                    raise AppError(
                        FILE_TOO_LARGE,
                        f"文件过大：{f.filename}（{len(content)} > {max_bytes} bytes）",
                        retriable=False,
                    )
                parser = get_parser(f.filename)
                files_texts.append(parser.parse(content, f.filename))
                yield _sse(
                    EVENT_PROGRESS,
                    ProgressEvent(
                        stage="parse",
                        percent=5 + int(80 * idx / max(len(files), 1)),
                        message=f"已解析 {idx}/{len(files)}：{f.filename}",
                    ).model_dump(),
                )

            # 3) progress: build_prompt
            yield _sse(
                EVENT_PROGRESS,
                ProgressEvent(stage="build_prompt", percent=90, message="构造提示词").model_dump(),
            )

            system, user = prompt_builder.build(
                text=text,
                files_texts=files_texts,
                template=template,
                language=language,
                detail=detail,  # type: ignore[arg-type]
                role=role or None,
                feature_name=feature_name or None,
            )

            # 4) LLM 流式
            adapter = get_adapter()
            gen_cfg = get_generation_config()
            log.info(
                "start LLM stream (model=%s, temperature=%s, max_tokens=%s)",
                gen_cfg.model,
                gen_cfg.temperature,
                gen_cfg.max_tokens,
            )

            # 把 stream 放到一个独立 task 中，主协程持续检测断开并 cancel
            queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=64)
            finished = asyncio.Event()
            error_holder: list[BaseException] = []

            async def _pump() -> None:
                try:
                    async for delta in adapter.stream(system, user):
                        await queue.put(delta)
                except BaseException as exc:  # 记录原异常供主协程抛出
                    error_holder.append(exc)
                finally:
                    await queue.put(None)  # 哨兵
                    finished.set()

            stream_task = asyncio.create_task(_pump(), name=f"llm-stream-{request_id}")

            while True:
                if await request.is_disconnected():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except (asyncio.CancelledError, BaseException):  # noqa: BLE001
                        pass
                    raise AppError(
                        CLIENT_DISCONNECTED,
                        "客户端已断开连接",
                        retriable=False,
                    )

                # 非阻塞等下一个 chunk
                try:
                    delta = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    # 检查 stream task 是否已结束且 queue 空（避免最后空转）
                    if finished.is_set() and queue.empty():
                        break
                    continue

                if delta is None:
                    # 哨兵
                    break
                total_chars += len(delta)
                yield _sse(EVENT_CHUNK, ChunkEvent(delta=delta).model_dump())

            # 等 pump task 收尾（确认无未抛异常）
            if not finished.is_set():
                try:
                    await asyncio.wait_for(finished.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    stream_task.cancel()
            if error_holder:
                raise error_holder[0]

            # 5) done
            duration_ms = int((time.monotonic() - started_at) * 1000)
            yield _sse(
                EVENT_DONE,
                DoneEvent(
                    request_id=request_id,
                    total_chars=total_chars,
                    duration_ms=duration_ms,
                ).model_dump(),
            )
            log.info("done total_chars=%d duration_ms=%d", total_chars, duration_ms)

        except AppError as ae:
            log.warning("AppError code=%s msg=%s", ae.code, ae.message)
            yield _sse(EVENT_ERROR, ae.to_dict())
        except asyncio.CancelledError:
            # 客户端断开 / 请求被取消
            if stream_task is not None and not stream_task.done():
                stream_task.cancel()
            yield _sse(
                EVENT_ERROR,
                ErrorEvent(
                    code=CLIENT_DISCONNECTED,
                    message="客户端已断开连接",
                    retriable=False,
                ).model_dump(),
            )
            raise
        except Exception as exc:  # noqa: BLE001  —— 兜底，全局 handler 也会转
            log.exception("unexpected error: %s", exc)
            yield _sse(
                EVENT_ERROR,
                ErrorEvent(
                    code="INTERNAL",
                    message=str(exc) or exc.__class__.__name__,
                    retriable=False,
                ).model_dump(),
            )

    return EventSourceResponse(
        event_source(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def __generate_request_id() -> str:
    """生成请求 id（不直接 import uuid 以保持路由文件可独立 mock）。"""
    import uuid

    return uuid.uuid4().hex
