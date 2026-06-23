"""飞书 H5 JSAPI 相关接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.feishu.jssdk import build_jssdk_config
from app.feishu.share_store import consume, create

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feishu"])


class SharePayloadCreate(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    title: str = Field(default="PRD 文档", max_length=200)


@router.post("/feishu/share-payload")
async def feishu_create_share_payload(body: SharePayloadCreate) -> JSONResponse:
    """暂存待分享内容，返回 share_id 供飞书中转页拉取。"""
    share_id = create(body.text, body.title)
    return JSONResponse({"shareId": share_id})


@router.get("/feishu/share-payload/{share_id}")
async def feishu_get_share_payload(share_id: str) -> JSONResponse:
    """一次性读取分享内容（读后即删）。"""
    payload = consume(share_id)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content={"message": "分享内容不存在或已过期"},
        )
    return JSONResponse({"text": payload.text, "title": payload.title})


@router.get("/feishu/jssdk-config")
async def feishu_jssdk_config(
    url: str = Query(..., description="当前页面 URL（不含 # 片段）"),
) -> JSONResponse:
    """返回飞书 H5 JSAPI 鉴权参数；未配置应用凭证时 enabled=false。"""
    settings = get_settings()
    if not settings.feishu_enabled:
        return JSONResponse({"enabled": False})

    if not url or "#" in url:
        return JSONResponse(
            status_code=400,
            content={"enabled": False, "message": "url 无效"},
        )

    try:
        config = await build_jssdk_config(
            settings.feishu_app_id,  # type: ignore[arg-type]
            settings.feishu_app_secret,  # type: ignore[arg-type]
            url,
        )
        return JSONResponse(config)
    except Exception as exc:
        logger.exception("feishu jssdk-config failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"enabled": False, "message": str(exc)},
        )
