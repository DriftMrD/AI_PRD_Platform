"""FastAPI 入口：lifespan、CORS、全局异常 handler、健康检查。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import AppError, INTERNAL
from app.prompts.skill_loader import preload as preload_skill_and_template
from app.routers.generate import router as generate_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用 lifespan：启动期预加载 SKILL 与模板；fail-fast。"""
    # 触发 pydantic-settings 构造，缺失 LLM_API_KEY 时直接抛错
    settings = get_settings()
    logger.info("startup: settings loaded (provider=%s, model=%s)",
                settings.llm_provider, settings.llm_model)
    preload_skill_and_template()
    logger.info("startup: SKILL.md & prd-template.md loaded")
    try:
        yield
    finally:
        logger.info("shutdown: bye")


app = FastAPI(
    title="PRD Forge Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(generate_router, prefix="/api")


# ===== 全局异常 handler =====
@app.exception_handler(AppError)
async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """未在 SSE 流中处理掉的 AppError：转 JSON（与 SSE error data 同 schema）。"""
    return JSONResponse(status_code=200, content=exc.to_dict())


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：未捕获异常统一转 `INTERNAL`。"""
    logger.exception("unhandled exception: %s", exc)
    return JSONResponse(
        status_code=200,
        content={"code": INTERNAL, "message": str(exc) or exc.__class__.__name__, "retriable": False},
    )


# ===== 健康检查 =====
@app.get("/")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
