"""SSE 事件 Pydantic 模型 + 5 个事件名常量集中。

事件名字符串严格在文件顶部定义，路由 / 全局 handler 仅引用本模块。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ===== 事件名常量（唯一权威来源）=====
EVENT_START = "start"
EVENT_PROGRESS = "progress"
EVENT_CHUNK = "chunk"
EVENT_DONE = "done"
EVENT_ERROR = "error"

EventName = Literal["start", "progress", "chunk", "done", "error"]


class StartEvent(BaseModel):
    """`start` 事件 data。"""

    request_id: str
    ts: float


class ProgressEvent(BaseModel):
    """`progress` 事件 data。

    Attributes:
        stage: 当前阶段名（parse / build_prompt / llm）。
        percent: 0-100 整数。
        message: 人类可读描述。
    """

    stage: str
    percent: int = Field(ge=0, le=100)
    message: str


class ChunkEvent(BaseModel):
    """`chunk` 事件 data。"""

    delta: str


class DoneEvent(BaseModel):
    """`done` 事件 data。"""

    request_id: str
    total_chars: int
    duration_ms: int


class ErrorEvent(BaseModel):
    """`error` 事件 data。"""

    code: str
    message: str
    retriable: bool = False


# 类型联合：路由层序列化时只需 `model_dump_json()`
SSEEvent = StartEvent | ProgressEvent | ChunkEvent | DoneEvent | ErrorEvent
