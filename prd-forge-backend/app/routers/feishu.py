"""飞书相关接口：分享、JSSDK、联系人搜索、文件发送。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.feishu.feishu_contacts import search_contacts
from app.feishu.jssdk import build_jssdk_config
from app.feishu.send_file import send_md_file_to_user
from app.feishu.share_store import consume, create

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feishu"])


# --------------- 请求模型 ---------------

class SharePayloadCreate(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    title: str = Field(default="PRD 文档", max_length=200)


class SearchContactsRequest(BaseModel):
    query: str = Field(min_length=1, max_length=50, description="搜索联系人姓名")


class ShareFileRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000, description="MD 文件内容")
    title: str = Field(default="PRD 文档", max_length=200, description="文件标题（不含扩展名）")
    version_label: str | None = Field(default=None, max_length=20, description="版本号如 v3")
    recipient_open_id: str = Field(..., description="收件人飞书 open_id")


# --------------- H5 JSAPI 分享（已有） ---------------

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


# --------------- 新增：联系人搜索 ---------------

@router.post("/feishu/search-contacts")
async def feishu_search_contacts(body: SearchContactsRequest) -> JSONResponse:
    """按姓名搜索飞书联系人。"""
    result = await search_contacts(body.query)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error_message or "搜索失败")
    return JSONResponse(result.data)


@router.post("/feishu/debug-search")
async def feishu_debug_search(body: SearchContactsRequest) -> JSONResponse:
    """调试：返回飞书 API 原始响应 + 解析后的用户数据。"""
    from app.feishu import openapi as _oa

    # 1) contact/v3/users 批量搜索
    raw1 = await _oa._feishu_get(
        "/contact/v3/users",
        params={"page_size": 3, "name": body.query},
    )
    items1 = raw1.get("data", {}).get("items", [])
    open_ids = [it.get("open_id") for it in items1 if it.get("open_id")]

    # 2) 逐个用 GET /contact/v3/users/:user_id 查详情
    user_details = {}
    for oid in open_ids[:2]:
        try:
            detail = await _oa._feishu_get(
                f"/contact/v3/users/{oid}",
                params={"user_id_type": "open_id"},
            )
            user_details[oid] = detail
        except Exception as e:
            user_details[oid] = {"error": str(e)}

    return JSONResponse({
        "contact_v3_users": {
            "first_item": items1[0] if items1 else None,
            "count": len(items1),
        },
        "user_details_by_open_id": user_details,
    })


# --------------- 新增：发送 MD 文件 ---------------

@router.post("/feishu/share-file")
async def feishu_share_file(body: ShareFileRequest) -> JSONResponse:
    """将 MD 内容作为文件发送给指定飞书用户。"""
    result = await send_md_file_to_user(
        user_open_id=body.recipient_open_id,
        content=body.content,
        title=body.title,
        version_label=body.version_label,
    )
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error_message or "发送失败")
    return JSONResponse(result.data)
