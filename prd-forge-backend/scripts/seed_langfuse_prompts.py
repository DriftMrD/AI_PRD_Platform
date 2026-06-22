#!/usr/bin/env python3
"""把仓库根的 skill / 模板 / system preamble 上传到 Langfuse。

用法（在 prd-forge-backend 目录）：
    python scripts/seed_langfuse_prompts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langfuse import Langfuse

from app.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_DOCUMENT_PATH = _REPO_ROOT / "skill-document.md"
_SKILL_DIALOGUE_PATH = _REPO_ROOT / "skill-dialogue.md"
_TEMPLATE_PATH = _REPO_ROOT / "prd-template.md"
_SYSTEM_PREAMBLE_PATH = _REPO_ROOT / "prd-system-preamble.md"


def _read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        raise SystemExit(
            "请先在 .env 配置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY"
        )

    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_base_url,
    )

    generation_config = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }

    seeds: list[tuple[str, str, dict | None]] = [
        (settings.langfuse_skill_document_prompt_name, _read(_SKILL_DOCUMENT_PATH), None),
        (settings.langfuse_skill_dialogue_prompt_name, _read(_SKILL_DIALOGUE_PATH), None),
        (settings.langfuse_template_prompt_name, _read(_TEMPLATE_PATH), None),
        (
            settings.langfuse_system_prompt_name,
            _read(_SYSTEM_PREAMBLE_PATH),
            generation_config,
        ),
    ]

    for name, content, config in seeds:
        langfuse.create_prompt(
            name=name,
            type="text",
            prompt=content,
            labels=["production"],
            config=config,
        )
        extra = f", config={config}" if config else ""
        print(f"✓ uploaded `{name}` ({len(content)} chars) → production{extra}")

    langfuse.flush()
    print("\n完成。")
    print("提示：旧的 prd-skill 已废弃，请在 Langfuse 删除或归档。")
    print("当前使用：prd-skill-document · prd-skill-dialogue · prd-system · prd-template")


if __name__ == "__main__":
    main()
