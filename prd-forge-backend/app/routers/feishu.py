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
    _set_token_cookies,
    create_session,
)
from app.feishu.send_file import send_md_file_to_user
from app.feishu.share_store import consume, create

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feishu"])


# --------------- 请求模型 ---------------

class SharePayloadCreate(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    title: str = Field(default="PRD 文档", max_length=200)


class OAuthStatusRequest(BaseModel):
    feishu_session: str | None = Field(default=None, description="OAuth session token（绕过跨站 Cookie）")


class SearchContactsRequest(BaseModel):
    query: str = Field(min_length=1, max_length=50, description="搜索联系人姓名")
    feishu_session: str | None = Field(default=None, description="OAuth session token（绕过跨站 Cookie）")


class ShareFileRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000, description="MD 文件内容")
    title: str = Field(default="PRD 文档", max_length=200, description="文件标题（不含扩展名）")
    version_label: str | None = Field(default=None, max_length=20, description="版本号如 v3")
    recipient_open_id: str = Field(..., description="收件人飞书 open_id")
    feishu_session: str | None = Field(default=None, description="OAuth session token（绕过跨站 Cookie）")


# --------------- OAuth 授权 ---------------

def _oauth_status_payload(request: Request, feishu_session: str | None) -> dict:
    """根据 session token / cookie 判断授权状态。"""
    token = extract_user_token_from_request(request, session_token=feishu_session)
    if token:
        return {"authorized": True}
    try:
        authorize_url = build_authorize_url()
    except RuntimeError:
        authorize_url = None
    return {"authorized": False, "authorize_url": authorize_url}


@router.get("/feishu/oauth/status")
async def feishu_oauth_status(
    request: Request,
    feishu_session: str | None = Query(default=None, description="OAuth session token"),
) -> JSONResponse:
    """检查用户是否已授权飞书（GET，兼容旧前端）。"""
    return JSONResponse(_oauth_status_payload(request, feishu_session))


@router.post("/feishu/oauth/status")
async def feishu_oauth_status_post(
    body: OAuthStatusRequest,
    request: Request,
) -> JSONResponse:
    """检查用户是否已授权飞书（POST，推荐：可传较长 session token）。"""
    return JSONResponse(_oauth_status_payload(request, body.feishu_session))


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

    # 重定向回前端，携带 session token（绕过跨站 Cookie 拦截；必须 URL 编码）
    import urllib.parse

    session_token = create_session(token_data)
    frontend_url = get_settings().feishu_oauth_frontend_url
    redirect_url = (
        f"{frontend_url}?auth_ok=1"
        f"&feishu_session={urllib.parse.quote(session_token, safe='')}"
    )
    if state:
        redirect_url += f"&state={state}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_token_cookies(response, token_data)  # cookie 保底（同域时有效）
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
    """按姓名搜索飞书联系人（优先用户身份 token，可拿到真实姓名）。"""
    user_token = extract_user_token_from_request(request, session_token=body.feishu_session)
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
