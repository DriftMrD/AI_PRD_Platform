---
name: prd-convert-to-template
description: Converts PRDs in arbitrary formats into the repository's prd-template.md structure (sections 元信息 through 变更历史). Use when the user asks to normalize a PRD, convert PRD to template format, match prd-template, reduce /prd-import loss, or restyle an existing PRD document.
---

# PRD → prd-template 转换

将任意形态的 PRD（大纲混乱、只有 UI 说明、混写业务规则等）重组为仓库根目录 **`prd-template.md`** 定义的章节与排版。**转换前必须先读取 `prd-template.md`**，输出与之同级标题、表格与列表风格一致。

## 输入与输出

- **输入**：用户指定的 PRD 文件路径、粘贴正文、或当前对话中的 PRD 草稿。
- **输出**：一份完整 Markdown：从 `# <feature_name> PRD` 到 `## 变更历史`，结构与 `prd-template.md` 对齐（保留模板中的中英文小节标题与分隔线 `---`）。

## 核心原则

1. **保真搬运**：原文中的规则、数字、枚举、SDK 字段名、埋点名等必须保留，不改写含义。
2. **推断须标注**：模板里没有而必须从上下文补全的内容，在对应段落用 **`> 【ai_inferred】`** 单行引用标注原因；或在表格单元格内写「待确认」并同样标注。
3. **禁止编造决策**：商业优先级、明确日期、未给出的 API/版本号——勿捏造；用占位符或「待 PM 填写」。
4. **用户故事与场景**：若原文是「场景 A/B/C」或交互说明，映射到 **§3**，拆成若干 Story；每个 Story 至少包含主流程 + 一条边界或异常 Scenario，使用 **GIVEN / WHEN / THEN / AND**。
5. **范围**：原文中的「不做」「后续」「本期」归类到 **§2.2 / §2.3**；本期交付列入 **§2.1**。

## 章节映射（常见来源 → 模板位置）

| 原文常见块 | 目标章节 |
|-----------|---------|
| 版本、负责人、链接、AR | 元信息表 |
| 背景、目标、Why、痛点 | §1（1.1～1.3） |
| In/Out scope、本期/下期 | §2 |
| 用户故事、场景、用例、流程 | §3 |
| UI、Figma、控件、交互 | §4 |
| 验收、Definition of Done | §5 |
| SDK、依赖、兼容、性能、网络、隐私、权限 | §6 |
| 风险、已知问题 | §7 |
| 竞品、wiki、历史文档 | §8 |
| （新建转换） | 变更历史：一行初版 |

## 执行步骤

1. **Read** `prd-template.md`（仓库根目录），确认标题层级与表格列名。
2. **Read** 待转换 PRD 全文，列出事实清单（规则列表、状态机、埋点表等），避免遗漏。
3. 拟定 **`# <feature_name> PRD`** 标题：`feature_name` 取自原文标题或核心功能名，简洁可读。
4. 按模板顺序填空：**元信息**能填则填；缺失项留空或写 `-`，勿猜 PM 姓名。
5. **§3** 优先：把分散的「界面/场景」收成 Story；Scenario 标题用 `Scenario 3.x.y` 连续编号。
6. **§4**：若原文只有「图 1、图 2」而无 Figma 链接，表格里节点 ID 可空，**【ai_inferred】** 注明「待补充 Figma」。
7. **§5**：验收项从原文「规则」「必须」「不应」转化可为勾选列表；尽量可验收、可测试。
8. 全文检查：分隔线、表格对齐、列表层级与模板一致；删除仅服务于旧格式的冗余编号（如重复的「3.1」），改为模板编号体系。

## 可选：与 `/prd-import` 的配合

模板顶部说明：按模板撰写可降低导入损耗。转换完成后可提示用户：后续若有自动化导入步骤，优先使用本结构。

## 额外资源

- canonical 结构定义：仓库根目录下的 `prd-template.md`（与本 skill 相对路径 `../../../prd-template.md`）
