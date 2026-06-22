"""Prompt 构建器：拼装 `system` + `user` 消息。

拼接规则：
- user：text → files_texts[0] → files_texts[1] → …
- system：输出格式约束 + 自动选定的 SKILL + 模板 + 本次参数
- SKILL 选用：有附件内容 → document；否则 → dialogue（前端无感）
"""

from __future__ import annotations

from typing import Iterable

from app.prompts.skill_loader import (
    SkillMode,
    get_skill_text,
    get_system_preamble_text,
    get_template_text,
)

_SKILL_MODE_LABELS: dict[SkillMode, str] = {
    "document": "文档转换（有附件，含补充说明）",
    "dialogue": "对话提炼（纯文本）",
}


def resolve_skill_mode(
    text: str,
    files_texts: Iterable[str],
) -> SkillMode:
    """根据输入自动选定 SKILL 类型。"""
    if any((ft or "").strip() for ft in files_texts):
        return "document"
    return "dialogue"


def _format_meta_block(
    *,
    skill_mode: SkillMode,
    template: str,
    language: str,
    detail: str,
    role: str | None,
    feature_name: str | None,
) -> str:
    """构造 system 中的元信息段落。"""
    lines: list[str] = [
        f"- 转换模式: {_SKILL_MODE_LABELS[skill_mode]}（系统自动选定）",
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
    """拼装 system 与 user 消息。"""
    files_list = list(files_texts)
    skill_mode = resolve_skill_mode(text, files_list)
    skill = get_skill_text(skill_mode)
    template_body = get_template_text()
    preamble = get_system_preamble_text()

    meta = _format_meta_block(
        skill_mode=skill_mode,
        template=template,
        language=language,
        detail=detail,
        role=role,
        feature_name=feature_name,
    )

    system = (
        f"{preamble.strip()}\n\n"
        f"## 转换规则（SKILL · {skill_mode}）\n"
        f"{skill}\n\n"
        "## 输出模板\n"
        f"{template_body}\n\n"
        "## 本次参数\n"
        f"{meta}\n"
    )

    parts: list[str] = []
    has_files = any((ft or "").strip() for ft in files_list)
    if text and text.strip():
        label = "补充说明" if has_files else "用户原始需求"
        parts.append(f"【{label}】\n{text.strip()}")
    for idx, ft in enumerate(files_list, start=1):
        ft_clean = (ft or "").strip()
        if not ft_clean:
            continue
        parts.append(f"【附件 {idx}】\n{ft_clean}")
    if not parts:
        parts.append("（无任何输入）")
    user = "\n\n".join(parts)

    return system, user
