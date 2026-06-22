"""加载 SKILL 与 PRD 模板。

来源（二选一）：
- Langfuse：配置 `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` 后，从云端拉取 prompt。
- 本地文件：仓库根的 skill-*.md 与 prd-template.md（启动期读入内存）。

Skill 按输入类型自动选用（document / dialogue），由 `builder` 决定，前端无感。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.config import Settings, get_settings
from app.models.generation_config import GenerationConfig

SkillMode = Literal["document", "dialogue"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_DOCUMENT_PATH = _REPO_ROOT / "skill-document.md"
_SKILL_DIALOGUE_PATH = _REPO_ROOT / "skill-dialogue.md"
_TEMPLATE_PATH = _REPO_ROOT / "prd-template.md"
_SYSTEM_PREAMBLE_PATH = _REPO_ROOT / "prd-system-preamble.md"

_skill_document_text: str | None = None
_skill_dialogue_text: str | None = None
_template_text: str | None = None
_system_preamble_text: str | None = None
_langfuse_client: object | None = None


def _skill_prompt_name(settings: Settings, mode: SkillMode) -> str:
    if mode == "document":
        return settings.langfuse_skill_document_prompt_name
    return settings.langfuse_skill_dialogue_prompt_name


def _get_langfuse_client(settings: Settings):
    """懒初始化 Langfuse 客户端。"""
    global _langfuse_client
    if _langfuse_client is None:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
        )
    return _langfuse_client


def _fetch_langfuse_prompt(settings: Settings, name: str) -> str:
    """从 Langfuse 拉取 text prompt 正文。"""
    prompt = _get_langfuse_prompt_object(settings, name)
    body = getattr(prompt, "prompt", None)
    if not body or not str(body).strip():
        raise RuntimeError(
            f"Langfuse prompt `{name}`（label={settings.langfuse_prompt_label}）内容为空"
        )
    return str(body)


def _get_langfuse_prompt_object(settings: Settings, name: str):
    """从 Langfuse 拉取 prompt 对象（含 config）。"""
    client = _get_langfuse_client(settings)
    return client.get_prompt(
        name,
        label=settings.langfuse_prompt_label,
        cache_ttl_seconds=settings.langfuse_cache_ttl_seconds,
    )


def _generation_config_from_settings(settings: Settings) -> GenerationConfig:
    """从环境变量构造生成参数（Langfuse 未启用或 config 缺项时的兜底）。"""
    return GenerationConfig(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


def get_generation_config() -> GenerationConfig:
    """返回 LLM 生成参数。

    Langfuse 启用时优先读 `prd-system` prompt 的 config JSON；
    缺项回退到 `.env` 中的 `LLM_MODEL` / `LLM_TEMPERATURE` / `LLM_MAX_TOKENS`。
    """
    settings = get_settings()
    fallback = _generation_config_from_settings(settings)
    if not settings.langfuse_enabled:
        return fallback

    prompt = _get_langfuse_prompt_object(settings, settings.langfuse_system_prompt_name)
    cfg = getattr(prompt, "config", None)
    if not isinstance(cfg, dict) or not cfg:
        return fallback

    model = cfg.get("model") or fallback.model
    temperature = cfg.get("temperature", fallback.temperature)
    max_tokens = cfg.get("max_tokens", fallback.max_tokens)

    if temperature is not None:
        temperature = float(temperature)
    if max_tokens is not None:
        max_tokens = int(max_tokens)

    return GenerationConfig(
        model=str(model),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _load_local_files() -> None:
    """从仓库根读取本地 Markdown 文件。"""
    global _skill_document_text, _skill_dialogue_text, _template_text, _system_preamble_text
    for path in (
        _SKILL_DOCUMENT_PATH,
        _SKILL_DIALOGUE_PATH,
        _TEMPLATE_PATH,
        _SYSTEM_PREAMBLE_PATH,
    ):
        if not path.is_file():
            raise RuntimeError(f"启动失败：仓库根缺少 {path.name}（期望路径 {path}）")
    try:
        _skill_document_text = _SKILL_DOCUMENT_PATH.read_text(encoding="utf-8")
        _skill_dialogue_text = _SKILL_DIALOGUE_PATH.read_text(encoding="utf-8")
        _template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
        _system_preamble_text = _SYSTEM_PREAMBLE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"启动失败：读取 SKILL/模板异常：{exc}") from exc


def preload() -> None:
    """启动期调用：校验 prompt 来源可用（fail-fast）。"""
    settings = get_settings()
    if settings.langfuse_enabled:
        get_skill_text("document")
        get_skill_text("dialogue")
        get_template_text()
        get_system_preamble_text()
        get_generation_config()
        return
    _load_local_files()


def get_skill_text(mode: SkillMode) -> str:
    """返回指定类型的 SKILL 正文。"""
    settings = get_settings()
    if settings.langfuse_enabled:
        return _fetch_langfuse_prompt(settings, _skill_prompt_name(settings, mode))

    if mode == "document":
        if _skill_document_text is None:
            raise RuntimeError("skill-document.md 尚未加载")
        return _skill_document_text

    if _skill_dialogue_text is None:
        raise RuntimeError("skill-dialogue.md 尚未加载")
    return _skill_dialogue_text


def get_template_text() -> str:
    """返回 PRD 模板正文。"""
    settings = get_settings()
    if settings.langfuse_enabled:
        return _fetch_langfuse_prompt(
            settings, settings.langfuse_template_prompt_name
        )

    if _template_text is None:
        raise RuntimeError(
            "prd-template.md 尚未加载（请确认 lifespan 中已调用 preload()）"
        )
    return _template_text


def get_system_preamble_text() -> str:
    """返回 system prompt 输出格式约束。"""
    settings = get_settings()
    if settings.langfuse_enabled:
        return _fetch_langfuse_prompt(
            settings, settings.langfuse_system_prompt_name
        )

    if _system_preamble_text is None:
        raise RuntimeError(
            "prd-system-preamble.md 尚未加载（请确认 lifespan 中已调用 preload()）"
        )
    return _system_preamble_text


def prompt_source() -> str:
    """当前 prompt 来源描述（用于启动日志）。"""
    settings = get_settings()
    if settings.langfuse_enabled:
        return (
            f"langfuse ({settings.langfuse_base_url}, "
            f"skills={settings.langfuse_skill_document_prompt_name}|"
            f"{settings.langfuse_skill_dialogue_prompt_name}, "
            f"template={settings.langfuse_template_prompt_name}, "
            f"system={settings.langfuse_system_prompt_name}, "
            f"label={settings.langfuse_prompt_label})"
        )
    return (
        f"local ({_SKILL_DOCUMENT_PATH.name}, {_SKILL_DIALOGUE_PATH.name}, "
        f"{_TEMPLATE_PATH.name}, {_SYSTEM_PREAMBLE_PATH.name})"
    )


def reset_for_tests() -> None:
    """QA 阶段使用：清空模块级状态。"""
    global _skill_document_text, _skill_dialogue_text, _template_text
    global _system_preamble_text, _langfuse_client
    _skill_document_text = None
    _skill_dialogue_text = None
    _template_text = None
    _system_preamble_text = None
    _langfuse_client = None
