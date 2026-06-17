"""启动期加载仓库根的 `SKILL.md` 与 `prd-template.md`。

行为约束：
- 启动期由 `app/main.py` 的 lifespan 调用 `preload()` 一次性读取。
- 缺失文件抛 `RuntimeError`，阻止 app 启动。
- 暴露 `get_skill_text()` / `get_template_text()`，请求期不再 I/O。
- 提供 `reset_for_tests()` 供 QA 阶段替换内容使用。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# 仓库根 = 本文件所在目录的上三级（prd-forge-backend/app/prompts/skill_loader.py
# → ../../../../  = AI_PRD_Platform/）
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_PATH = _REPO_ROOT / "SKILL.md"
_TEMPLATE_PATH = _REPO_ROOT / "prd-template.md"

_skill_text: str | None = None
_template_text: str | None = None


def preload() -> None:
    """启动期调用：读取两个文件到 module 级变量。

    Raises:
        RuntimeError: 任一文件缺失或读取失败。
    """
    global _skill_text, _template_text
    if not _SKILL_PATH.is_file():
        raise RuntimeError(
            f"启动失败：仓库根缺少 SKILL.md（期望路径 {_SKILL_PATH}）"
        )
    if not _TEMPLATE_PATH.is_file():
        raise RuntimeError(
            f"启动失败：仓库根缺少 prd-template.md（期望路径 {_TEMPLATE_PATH}）"
        )
    try:
        _skill_text = _SKILL_PATH.read_text(encoding="utf-8")
        _template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"启动失败：读取 SKILL/模板异常：{exc}") from exc


@lru_cache(maxsize=1)
def get_skill_text() -> str:
    """返回已加载的 SKILL.md 内容。

    Raises:
        RuntimeError: 未先调用 `preload()`。
    """
    if _skill_text is None:
        raise RuntimeError("SKILL.md 尚未加载（请确认 lifespan 中已调用 preload()）")
    return _skill_text


@lru_cache(maxsize=1)
def get_template_text() -> str:
    """返回已加载的 prd-template.md 内容。

    Raises:
        RuntimeError: 未先调用 `preload()`。
    """
    if _template_text is None:
        raise RuntimeError(
            "prd-template.md 尚未加载（请确认 lifespan 中已调用 preload()）"
        )
    return _template_text


def reset_for_tests() -> None:
    """QA 阶段使用：清空模块级状态。"""
    global _skill_text, _template_text
    _skill_text = None
    _template_text = None
    get_skill_text.cache_clear()
    get_template_text.cache_clear()
