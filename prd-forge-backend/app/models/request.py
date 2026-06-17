"""`POST /api/generate` 的请求模型（不含 `files` 字段，文件由 FastAPI UploadFile 单独处理）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Detail = Literal["concise", "standard", "full"]


class GenerateRequest(BaseModel):
    """multipart form 字段映射对象。

    字段命名严格与前端 form-data 一一对应。
    """

    text: str = Field(default="", description="用户原始需求文本")
    template: str = Field(default="standard", description="模板键名（占位，预留扩展）")
    language: str = Field(default="zh", description="输出语言，如 zh / en")
    detail: Detail = Field(default="standard", description="详尽度")
    role: str | None = Field(default=None, description="目标角色，如 产品经理")
    feature_name: str | None = Field(default=None, description="特性名（用于标题/章节锚定）")
