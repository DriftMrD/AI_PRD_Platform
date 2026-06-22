---
name: prd-convert-to-template
description: Converts PRDs in arbitrary formats into the repository's prd-template.md structure. Two runtime skills — document (file upload) and dialogue (conversation) — are selected automatically by the backend; see skill-document.md and skill-dialogue.md.
---

# PRD Forge Skills

后端按输入类型自动选用，无需用户选择：

| 输入 | Skill 文件 | Langfuse 名称 |
|------|-----------|---------------|
| 有附件文档 | `skill-document.md` | `prd-skill-document` |
| 仅对话/文本 | `skill-dialogue.md` | `prd-skill-dialogue` |

- **文档转换**：`skill-document.md` — 保真重组已有 PRD/需求文档
- **对话提炼**：`skill-dialogue.md` — 从多轮口语化需求归纳 PRD

输出模板：`prd-template.md` · 输出格式约束：`prd-system-preamble.md`（Langfuse `prd-system`）
