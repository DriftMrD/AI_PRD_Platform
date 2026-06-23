"""应用配置（pydantic-settings）。

设计要点：
- fail-fast：缺失 `LLM_API_KEY` 时构造 `Settings()` 即抛 `ValidationError`。
- 单例：模块级 `_settings` 缓存，启动期解析一次，路由只读。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量 / .env 读取的应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["openai"] = Field(default="openai", alias="LLM_PROVIDER")
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1", alias="LLM_BASE_URL"
    )
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=20000, alias="LLM_MAX_TOKENS")
    llm_timeout_s: float = Field(default=120.0, alias="LLM_TIMEOUT_S")
    llm_first_token_timeout_s: float = Field(
        default=30.0, alias="LLM_FIRST_TOKEN_TIMEOUT_S"
    )

    # 文件 / 解析
    max_file_size_mb: int = Field(default=20, alias="MAX_FILE_SIZE_MB")
    max_file_chars: int = Field(default=50_000, alias="MAX_FILE_CHARS")

    # CORS
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # Langfuse Prompt Management（可选；配齐 public + secret key 后启用）
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com", alias="LANGFUSE_BASE_URL"
    )
    langfuse_skill_document_prompt_name: str = Field(
        default="prd-skill-document", alias="LANGFUSE_SKILL_DOCUMENT_PROMPT_NAME"
    )
    langfuse_skill_dialogue_prompt_name: str = Field(
        default="prd-skill-dialogue", alias="LANGFUSE_SKILL_DIALOGUE_PROMPT_NAME"
    )
    langfuse_template_prompt_name: str = Field(
        default="prd-template", alias="LANGFUSE_TEMPLATE_PROMPT_NAME"
    )
    langfuse_system_prompt_name: str = Field(
        default="prd-system", alias="LANGFUSE_SYSTEM_PROMPT_NAME"
    )
    langfuse_prompt_label: str = Field(
        default="production", alias="LANGFUSE_PROMPT_LABEL"
    )
    langfuse_cache_ttl_seconds: int = Field(
        default=60, alias="LANGFUSE_CACHE_TTL_SECONDS"
    )

    @field_validator("llm_api_key")
    @classmethod
    def _api_key_required(cls, v: str) -> str:
        """fail-fast：禁止空值。"""
        if not v or not v.strip():
            raise ValueError(
                "LLM_API_KEY 缺失或为空。\n"
                "  本地开发：cp .env.example .env  → 编辑 .env 填入 key\n"
                "  Render 部署：Dashboard → prd-forge-backend → Environment → Add Secret\n"
                "              Key=LLM_API_KEY  Value=sk-你的-key  → Save"
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        """逗号分隔的 CORS 来源字符串转列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        """`MAX_FILE_SIZE_MB` 转字节。"""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def langfuse_enabled(self) -> bool:
        """是否从 Langfuse 拉取 prompt（需同时配置 public + secret key）。"""
        return bool(
            self.langfuse_public_key
            and self.langfuse_public_key.strip()
            and self.langfuse_secret_key
            and self.langfuse_secret_key.strip()
        )

    # 飞书 H5 JSAPI（可选；配齐 app id + secret 后启用分享选人）
    feishu_app_id: str | None = Field(default=None, alias="FEISHU_APP_ID")
    feishu_app_secret: str | None = Field(default=None, alias="FEISHU_APP_SECRET")
    # 飞书 OAuth 回调地址（授权后将 code 送回后端）
    feishu_oauth_redirect_uri: str | None = Field(default=None, alias="FEISHU_OAUTH_REDIRECT_URI")

    @property
    def feishu_enabled(self) -> bool:
        """是否启用飞书 H5 JSAPI 鉴权。"""
        return bool(
            self.feishu_app_id
            and self.feishu_app_id.strip()
            and self.feishu_app_secret
            and self.feishu_app_secret.strip()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取（并缓存）单例配置。

    Raises:
        pydantic.ValidationError: 缺失 `LLM_API_KEY` 时抛出。
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        # 把 pydantic 字段名/错误信息原样抛上去，部署平台日志里一眼能看见
        import sys
        print(f"\n[CONFIG ERROR] {exc.__class__.__name__}: {exc}\n", file=sys.stderr)
        raise
