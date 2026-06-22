#!/usr/bin/env python3
"""把仓库根的 SKILL / 模板 / system preamble 上传到 Langfuse（一次性初始化）。

用法（在 prd-forge-backend 目录）：
    cp .env.example .env   # 填好 LANGFUSE_* key
    python scripts/seed_langfuse_prompts.py

会在 Langfuse 创建/更新 text prompt，并打上 production 标签。
`prd-system` 会附带 model / temperature / max_tokens config（来自 .env 兜底值）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许从 prd-forge-backend/ 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langfuse import Langfuse

from app.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_PATH = _REPO_ROOT / "SKILL.md"
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
        (settings.langfuse_skill_prompt_name, _read(_SKILL_PATH), None),
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
        print(f"✓ uploaded prompt `{name}` ({len(content)} chars) → production{extra}")

    langfuse.flush()
    print("\n完成。重启后端后即可从 Langfuse 拉取 prompt 与生成参数。")


if __name__ == "__main__":
    main()
