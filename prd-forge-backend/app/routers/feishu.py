"""飞书 H5 JSAPI 相关接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.feishu.jssdk import build_jssdk_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feishu"])


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
