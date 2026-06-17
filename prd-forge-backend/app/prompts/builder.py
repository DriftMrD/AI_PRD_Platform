"""Prompt 构建器：拼装 `system` + `user` 消息。

拼接规则（来自 ARCHITECTURE §6）：
- user：text → files_texts[0] → files_texts[1] → …
- system：注入 SKILL.md 与 prd-template.md 内容；并以受控段落体现
  detail / language / role / feature_name。
"""

from __future__ import annotations

from typing import Iterable

from app.prompts.skill_loader import get_skill_text, get_template_text


def _format_meta_block(
    *,
    template: str,
    language: str,
    detail: str,
    role: str | None,
    feature_name: str | None,
) -> str:
    """构造 system 中的元信息段落。"""
    lines: list[str] = [
        f"- 模板: {template}",
        f"- 输出语言: {language}",
        f"- 详尽度: {detail}",
    ]
    if role:
        lines.append(f"- 目标读者/角色: {role}")
    if feature_name:
        lines.append(f"- 特性名: {feature_name}")
    return "\n".join(lines)


def build(
    text: str,
    files_texts: Iterable[str],
    template: str,
    language: str,
    detail: str,
    role: str | None,
    feature_name: str | None,
) -> tuple[str, str]:
    """拼装 system 与 user 消息。

    Args:
        text: 用户原始输入。
        files_texts: 已解析的附件文本列表（按上传顺序）。
        template: 模板键。
        language: 输出语言。
        detail: 详尽度。
        role: 目标角色（可空）。
        feature_name: 特性名（可空）。

    Returns:
        `(system, user)` 二元组。
    """
    skill = get_skill_text()
    template_body = get_template_text()

    meta = _format_meta_block(
        template=template,
        language=language,
        detail=detail,
        role=role,
        feature_name=feature_name,
    )

    system = (
        "你是 PRD Forge，一个把用户原始需求转写为结构化产品需求文档（PRD）的助手。\n"
        "请严格遵循下方的「转换规则（SKILL）」与「输出模板」生成内容。\n\n"
        "## 转换规则（SKILL）\n"
        f"{skill}\n\n"
        "## 输出模板\n"
        f"{template_body}\n\n"
        "## 本次参数\n"
        f"{meta}\n"
    )

    # user 拼接：text → 附件 1 → 附件 2 → …
    parts: list[str] = []
    if text and text.strip():
        parts.append(f"【用户原始需求】\n{text.strip()}")
    for idx, ft in enumerate(files_texts, start=1):
        ft_clean = (ft or "").strip()
        if not ft_clean:
            continue
        parts.append(f"【附件 {idx}】\n{ft_clean}")
    if not parts:
        parts.append("（无任何输入）")
    user = "\n\n".join(parts)

    return system, user
