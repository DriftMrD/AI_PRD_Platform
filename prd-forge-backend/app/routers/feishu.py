"""飞书相关接口：分享、JSSDK、OAuth 授权、联系人搜索、文件发送。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.feishu.feishu_contacts import search_contacts
from app.feishu.jssdk import build_jssdk_config
from app.feishu.oauth import (
    build_authorize_url,
    exchange_code,
    extract_user_token_from_request,
    store_token,
)
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


# --------------- OAuth 授权 ---------------

@router.get("/feishu/oauth/status")
async def feishu_oauth_status(request: Request) -> JSONResponse:
    """检查用户是否已授权飞书。"""
    token = extract_user_token_from_request(request)
    if token:
        return JSONResponse({"authorized": True})
    return JSONResponse({
        "authorized": False,
        "authorize_url": build_authorize_url(),
    })


@router.get("/feishu/oauth/callback")
async def feishu_oauth_callback(
    code: str = Query(...),
    state: str = Query(default=""),
) -> RedirectResponse:
    """飞书 OAuth 回调：用 code 换 token → 写 cookie → 重定向回首页。"""
    try:
        token_data = await exchange_code(code)
    except Exception as exc:
        logger.exception("OAuth token exchange failed: %s", exc)
        # 把错误信息编码到 URL，前端可解析展示
        import urllib.parse
        frontend_url = get_settings().feishu_oauth_frontend_url
        err_msg = urllib.parse.quote(str(exc)[:200])
        return RedirectResponse(url=f"{frontend_url}?auth_error={err_msg}", status_code=302)

    open_id = token_data.get("open_id", "")
    if open_id:
        store_token(open_id, token_data)

    # 重定向回前端（从配置读取前端地址，不要走相对路径）
    frontend_url = get_settings().feishu_oauth_frontend_url
    redirect_url = f"{frontend_url}?auth_ok=1"
    if state:
        redirect_url += f"&state={state}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    # 写 httpOnly cookie 存 open_id（token 本身存服务端缓存）
    # SameSite=None + Secure：允许跨站 POST（前端 GitHub Pages → 后端 Render API）
    response.set_cookie(
        key="feishu_user_open_id",
        value=open_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7200,
    )
    return response


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


# --------------- 联系人搜索 ---------------

@router.post("/feishu/search-contacts")
async def feishu_search_contacts(body: SearchContactsRequest, request: Request) -> JSONResponse:
    """按姓名搜索飞书联系人（有 user token 则返回真实姓名）。"""
    user_token = extract_user_token_from_request(request)
    result = await search_contacts(body.query, user_access_token=user_token)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error_message or "搜索失败")
    return JSONResponse(result.data)


# --------------- 发送 MD 文件 ---------------

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
