# PRD Forge 后台生成服务 - 产品需求文档

> 文档类型：简单 PRD（产品目标 + 用户故事 + 需求池 + 接口设计 + 待确认问题）
> 编写目的：指导 PRD Forge 后台（FastAPI + LLM 适配器 + SSE 流式输出）的开发落地
> 关联前端：仓库根目录 `index.html`（统一输入框 + 文件 chips + 生成配置 + 结果展示区，目前为 Mock）
> 关联资产：仓库根目录 `SKILL.md`（转换规则）、`prd-template.md`（目标结构）

---

## 1. 产品目标

PRD Forge 后台是「前台输入 → AI 重组 → 标准 PRD 输出」链路中的核心服务，承担两件事：

1. **把任意形态的需求原料（粘贴文本 / .md / .txt / .docx / .pdf）解析为可投递的 LLM 输入**——屏蔽格式差异，使前台只关心"我要写什么"，不关心"AI 怎么读"。
2. **按 `SKILL.md` 定义的规则，把原料重组为符合 `prd-template.md` 结构的标准 PRD，并通过 SSE 流式回推前台**——让用户从"读一段生成结果"变成"看 PRD 一步步长出来"，体感与可读性同步提升。

**业务价值**：把原本需要 30-90 分钟的手写/搬运工作压缩到 1-2 分钟，PM 只需上传原料+选配置，剩余的结构化、补全、推断标注全部由后台按既定规则完成。`【ai_inferred】` 标注机制确保 PM 始终掌握"哪些是 AI 猜的、哪些是原文事实"，避免黑盒信任。

**非目标（本期不做）**：不替代 PM 决策、不做 PRD 评审/版本管理、不做团队协作（评论/批注/权限）、不存储任何用户输入或生成结果到数据库（无持久化需求）。

---

## 2. 用户故事

### Story 1：粘贴文本生成标准 PRD（核心场景）

**作为** 一名产品经理，**我希望** 在前台文本框粘贴一份口语化的需求描述，**以便** 快速得到一份符合 `prd-template.md` 结构的 PRD 草稿。

**Scenario 2.1.1 - 主流程**
- **GIVEN** 用户在文本框输入 200-5000 字需求描述且未上传文件
- **WHEN** 选择「标准模板 + 中文 + 标准详细程度 + 产品经理角色」并点击「生成 PRD 文档」
- **THEN** 后台通过 SSE 流式回推 Markdown 文本，前台 `<pre id="resultContent">` 逐字追加渲染
- **AND** 收到 `done` 事件后前台自动展示「复制」「下载」按钮并 Toast 成功提示

### Story 2：上传 .docx 散乱文档生成结构化 PRD（核心场景）

**作为** 一名产品经理，**我希望** 上传一份只有标题和 bullet 列表的 Word 草稿，**以便** 拿到带 §1-§8 完整章节、含 GIVEN/WHEN/THEN 场景的标准 PRD。

**Scenario 2.2.1 - 主流程**
- **GIVEN** 用户拖拽上传一个 ≤20MB 的 .docx 文件
- **WHEN** 提交生成
- **THEN** 后台解析 .docx → 提取纯文本 → 注入 `SKILL.md` + `prd-template.md` 提示词 → 调用 LLM → SSE 流式输出
- **AND** 原文事实（数字、规则、SDK 字段名）保真保留，缺失章节用 `> 【ai_inferred】` 标注

### Story 3：多文件 + 文本混合输入（边界场景）

**作为** 一名产品经理，**我希望** 同时上传 1 个 .pdf 参考资料 + 1 个 .md 旧 PRD + 附加一段文字补充说明，**以便** 后台能把多份原料合并转换为新 PRD。

**Scenario 2.3.1 - 主流程**
- **GIVEN** 用户上传 2-3 个文件（.md / .txt / .docx / .pdf 任一组合）并附加文本
- **WHEN** 提交生成
- **THEN** 后台按"文件名 → 文本"有序解析所有文件，**拼接顺序固定为：用户文本 → 附件 1 → 附件 2 → ...** 一并送入 LLM

### Story 4：LLM 调用异常时的优雅降级（异常场景）

**作为** 一名前台用户，**我希望** 在 LLM 接口超时/限流/鉴权失败时看到明确错误提示，**以便** 我知道是该重试还是该联系管理员。

**Scenario 2.4.1 - LLM 超时**
- **GIVEN** 单次生成请求超过 90 秒（可配置）
- **WHEN** LLM 未返回首个 token
- **THEN** 后台发送 `error` 事件（type=`timeout`），前台停止 spinner 并 Toast「生成超时，请重试」

**Scenario 2.4.2 - LLM 鉴权失败**
- **GIVEN** 后台未配置 LLM API Key 或 Key 失效
- **WHEN** 任意生成请求
- **THEN** 立即发送 `error` 事件（type=`llm_auth`），前台提示「服务暂时不可用，请联系管理员」，**不暴露** 具体 Key/Provider 信息

### Story 5：用户中途取消（异常场景）

**作为** 一名前台用户，**我希望** 在生成过程中能主动停止，**以便** 看到的是我能控制的中断状态而不是半截内容。

**Scenario 2.5.1 - 主动取消**
- **GIVEN** SSE 流正在接收 `chunk` 事件
- **WHEN** 用户关闭页面 / 刷新 / 前台调用 `EventSource.close()`
- **THEN** 后台在检测到客户端断开后取消 LLM 流式调用（关闭底层 HTTP 连接），释放资源

---

## 3. 需求池

### P0 - 必须有（本期交付）

| # | 需求 | 验收标准 |
|---|------|---------|
| P0-1 | **文件上传接口**：支持 `multipart/form-data` 接收 1-N 个文件 + 表单字段 | 单次请求 1-N 个文件，文件大小 ≤20MB（与前台一致），文件类型白名单 `.md` / `.txt` / `.docx` / `.pdf` |
| P0-2 | **多格式文件解析**：把上传文件统一提取为纯文本 | .md/.txt 原样读取；.docx 用 `python-docx` 提取段落与表格文本；.pdf 用 `pypdf` 或 `pdfplumber` 提取文本（含中文） |
| P0-3 | **LLM 适配器抽象层**：定义统一接口，支持后续切换不同 LLM 厂商 | 提供 `BaseLLMAdapter` 抽象类（`async def stream(system, user) -> AsyncIterator[str]`），实现至少 1 个可运行的 Provider（OpenAI 兼容协议），通过环境变量切换 |
| P0-4 | **SKILL + Template 提示词组装**：按规则把 `SKILL.md` + `prd-template.md` 拼成 system prompt，把用户原料作为 user prompt | system prompt 包含 `SKILL.md` 全文（保真搬运规则、章节映射表、执行步骤）+ `prd-template.md` 全文；user prompt 包含用户文本 + 按固定顺序拼接的附件内容 |
| P0-5 | **LLM 流式调用与转发**：用 OpenAI 兼容流式协议，逐 chunk 转发到 SSE | 后台从 LLM 拿到首个 delta 后立即发送 `start` 事件；后续每个 delta 发送 `chunk` 事件；流结束发送 `done` 事件 |
| P0-6 | **SSE 响应格式**：标准 `text/event-stream`，事件类型 `start` / `chunk` / `done` / `error` | 每个事件含 `id`（递增）、`event`（类型）、`data`（JSON 字符串），详见 §4 接口设计 |
| P0-7 | **错误处理**：覆盖文件格式不支持、文件超 20MB、文件解析失败、LLM 鉴权失败、LLM 超时、流中断 5 类异常 | 每类异常对应一个 `error` 事件子类型；前台可按子类型差异化提示；HTTP 层不返回 5xx（即使是 401 也用 200 + SSE error 事件，方便前台统一处理） |
| P0-8 | **健康检查接口**：`GET /api/health` | 返回 `{ "status": "ok", "llm_provider": "<name>", "version": "<x.y.z>" }`，供部署平台/LB 探活 |
| P0-9 | **配置管理**：通过环境变量注入 LLM API Key、Base URL、Model、生成超时等 | 不在代码中硬编码 Key；启动时校验必需变量，缺失则启动失败并打印明确错误 |

### P1 - 应该做（本期推荐交付）

| # | 需求 | 验收标准 |
|---|------|---------|
| P1-1 | **生成进度提示**：在前台 spinner 阶段给出阶段化文案 | 通过 SSE 发送 `progress` 事件，类型枚举：`parsing_files` / `building_prompt` / `calling_llm` / `streaming_output`；前台可选择消费并显示阶段提示 |
| P1-2 | **生成超时控制**：可配置 LLM 整体调用超时（默认 90s）和首 token 超时（默认 15s） | 超过任一阈值则中断流式调用，发送 `error` 事件（type=`timeout`） |
| P1-3 | **可取消请求**：客户端断开后取消 LLM 调用释放资源 | 用 `asyncio` + `Request.is_disconnected()` 监听，断开时 `await adapter.close()` |
| P1-4 | **生成结果可下载/复制（接口侧准备）**：后端支持把最终结果以纯文本形式重新拉取 | 在 `done` 事件 `data` 中返回 `prd_text` 完整内容 + `prd_length` 字符数 + `task_id`；前台已有的「复制」「下载」按钮无需改动即可工作 |
| P1-5 | **请求日志**：结构化日志记录每次生成的输入摘要（文件数、总字符数、模板/语言/详细度/角色配置、LLM 耗时、token 消耗估算、首 token 延迟） | 用 `loguru` 或 `structlog` 输出 JSON 行；不记录原始 PRD 内容（避免敏感信息落盘） |
| P1-6 | **CORS 配置**：允许前台域名跨域调用 | 默认放行 `localhost:5173` / `localhost:3000`；通过环境变量配置生产域名 |

### P2 - 未来做（下个迭代考虑）

| # | 需求 | 价值 |
|---|------|-----|
| P2-1 | **生成历史记录**：把每次生成结果存入数据库，支持「我的 PRD 历史」列表 | 解决"我刚才生成的 PRD 没复制就刷新了"的痛点 |
| P2-2 | **用户配置记忆**：记住用户上次选的模板/语言/详细度/角色 | 减少重复选择 |
| P2-3 | **多模板切换**：支持 standard / agile / detailed / onepage 4 套不同模板的 SKILL+Template 组合 | 当前仅需支持 standard，其他模板作为配置项预留 |
| P2-4 | **并发限流**：按用户/IP 做令牌桶限流 | 防止单用户刷量打爆 LLM 配额 |
| P2-5 | **多文件合并策略配置**：让用户选择「拼接」/「摘要」/「最新覆盖」 | 当用户上传多份历史 PRD 时灵活处理 |
| P2-6 | **生成结果对比**：同一原料用不同模板/详细度生成多份 | 帮助 PM 挑选最合适的输出 |
| P2-7 | **导出格式扩展**：除 Markdown 外支持导出 .docx / .pdf | 对接传统评审流程 |

---

## 4. 接口设计

### 4.1 `POST /api/generate`

**用途**：接收前台提交的多模态需求原料（文本 + 文件 + 配置），调用 LLM 流式生成标准 PRD，通过 SSE 实时回推。

**Content-Type**：`multipart/form-data`

**请求体字段**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 条件必填 | 用户在文本框输入的原始需求。**与 `files` 至少有一个非空**（与前台校验一致） |
| `files` | File[] (multipart) | 条件必填 | 上传文件列表，0-N 个。单个文件 ≤20MB；支持 `.md` / `.txt` / `.docx` / `.pdf` |
| `template` | string | 否，默认 `standard` | PRD 模板：枚举值 `standard` / `agile` / `detailed` / `onepage`，P0 阶段只实现 `standard` |
| `language` | string | 否，默认 `zh` | 输出语言：枚举值 `zh` / `en` / `bilingual` |
| `detail` | string | 否，默认 `standard` | 详细程度：枚举值 `concise` / `standard` / `detailed` / `exhaustive` |
| `role` | string | 否，默认 `pm` | 目标读者：枚举值 `pm` / `designer` / `developer` / `stakeholder` |
| `feature_name` | string | 否 | 用户给产品功能起的名字（用于 PRD `# <feature_name> PRD` 标题）。为空时由 LLM 推断 |

**响应**：`200 OK`，`Content-Type: text/event-stream; charset=utf-8`

**SSE 事件类型**：

#### 4.1.1 `start` - 任务开始
```json
{
  "task_id": "uuid-v4",
  "ts": 1718448000000,
  "template": "standard",
  "language": "zh"
}
```

#### 4.1.2 `progress` - 阶段进度（P1）
```json
{
  "task_id": "uuid-v4",
  "stage": "parsing_files",
  "message": "正在解析 2 个附件..."
}
```
stage 枚举：`parsing_files` / `building_prompt` / `calling_llm` / `streaming_output`

#### 4.1.3 `chunk` - PRD 文本流片段
```json
{
  "task_id": "uuid-v4",
  "delta": "## 1. 背景与动机",
  "index": 12
}
```
- `delta`：本次新增的 Markdown 文本片段（前台 append 到结果区）
- `index`：累计 chunk 序号（自增，前台可用于断点续传，本期可不消费）

#### 4.1.4 `done` - 任务完成
```json
{
  "task_id": "uuid-v4",
  "prd_text": "# <feature_name> PRD\n\n## 元信息\n...",
  "prd_length": 4521,
  "stats": {
    "llm_first_token_ms": 1240,
    "llm_total_ms": 18340,
    "input_chars": 3200,
    "files_parsed": 2
  }
}
```

#### 4.1.5 `error` - 任务失败
```json
{
  "task_id": "uuid-v4",
  "type": "timeout",
  "message": "LLM 调用超过 90 秒",
  "retryable": true
}
```
`type` 枚举：
- `file_too_large` - 单文件超 20MB
- `unsupported_format` - 文件类型不在白名单
- `file_parse_failed` - 文件解析异常（如加密 PDF、损坏 docx）
- `llm_auth` - LLM 鉴权失败
- `llm_rate_limit` - LLM 限流
- `llm_network` - LLM 网络异常
- `timeout` - 超时
- `internal` - 后台内部异常

**`retryable`**：告诉前台是否值得自动重试（`true` 用于 `timeout` / `llm_rate_limit` / `llm_network`；`false` 用于 `file_too_large` / `unsupported_format` / `llm_auth`）。

**示例事件流**（`data:` 后是 JSON 字符串）：
```
id: 1
event: start
data: {"task_id":"...","ts":...}

id: 2
event: progress
data: {"task_id":"...","stage":"parsing_files","message":"..."}

id: 3
event: progress
data: {"task_id":"...","stage":"calling_llm","message":"..."}

id: 4
event: chunk
data: {"task_id":"...","delta":"# ","index":1}

id: 5
event: chunk
data: {"task_id":"...","delta":"<feature_name> PRD\n\n","index":2}

...

id: 99
event: done
data: {"task_id":"...","prd_text":"...","prd_length":4521,"stats":{...}}
```

### 4.2 `GET /api/health`

**用途**：健康检查，供负载均衡 / 部署平台探活。

**响应**：
```json
{
  "status": "ok",
  "llm_provider": "openai",
  "version": "0.1.0",
  "ts": 1718448000000
}
```

**异常响应**（LLM 不可用但服务存活）：`200 OK` + `status: "degraded"`，明确告知 LLM 不可用。

### 4.3 错误响应约定

**HTTP 层**：所有可预期的错误（参数错误、文件过大等）**仍返回 200 + SSE error 事件**，因为 SSE 连接一旦建立就难以切换到错误页；只在请求本身无法建立（如 multipart 解析失败）时返回 4xx/5xx。

| 场景 | 响应 |
|------|------|
| `files` 和 `text` 都为空 | `400 Bad Request` + JSON `{ "error": "empty_input" }` |
| 文件超 20MB（超过在解析前） | `400 Bad Request` + JSON `{ "error": "file_too_large", "max_mb": 20 }` |
| Content-Type 不是 multipart | `415 Unsupported Media Type` |
| LLM 鉴权失败 | `200` + SSE `error` 事件（type=`llm_auth`） |
| 内部未捕获异常 | `500 Internal Server Error` + JSON `{ "error": "internal" }`（仅在 SSE 连接建立前） |

---

## 5. 提示词设计概要

> 工程师在实现时可按以下骨架填充具体措辞；本节是"应该让 LLM 看到什么"的契约，不是"必须用这段文字"。

### 5.1 System Prompt 结构

```
[ROLE]
你是一名资深产品经理助手，擅长把零散需求重组为符合标准模板的 PRD。

[TEMPLATE STRUCTURE]
<这里注入 prd-template.md 的完整内容>
（包含元信息表、§1-§8 全部小节标题、表格列名、列表风格）

[CONVERSION RULES - 来自 SKILL.md]
<这里注入 SKILL.md 的"核心原则"+"章节映射表"+"执行步骤"全部内容>
（包含保真搬运、ai_inferred 标注、禁止编造决策、用户故事 GIVEN/WHEN/THEN、范围分类等规则）

[OUTPUT FORMAT CONSTRAINTS]
- 输出纯 Markdown，不要包裹 ```markdown 代码块
- 章节标题、表格、分隔线（---）必须与模板一致
- 缺失信息用 `> 【ai_inferred】` 引用块标注原因
- 禁止编造 PM 姓名、AR ID、日期、API 版本号
- 语言：根据用户选择的 language 输出（zh / en / bilingual）
- 详细程度：根据用户选择的 detail 调整正文展开深度
- 目标读者：根据用户选择的 role 调整术语与详略（pm/designer/developer/stakeholder）

[QUALITY BAR]
- §3 用户故事至少 3 条，每条至少 1 主流程 + 1 边界/异常场景
- §4 UI 设计若原文无 Figma 链接，节点 ID 留空并标注「待补充 Figma」
- §5 验收项用 `- [ ]` checkbox 列表，可测试、可勾选
```

### 5.2 User Prompt 结构

```
请基于以下【需求原料】生成一份符合模板的 PRD。

【生成配置】
- 模板：{template}
- 语言：{language}
- 详细程度：{detail}
- 目标读者：{role}
- 功能名：{feature_name or "（请从原料推断）"}

【用户文本】
{text}

【附件 1：{filename}】
{file_1_extracted_text}

【附件 2：{filename}】
{file_2_extracted_text}

...

【输出要求】
- 直接输出 PRD 正文，从 `# {feature_name or '<feature_name>'} PRD` 开始
- 不输出任何前言/后语/解释
- 不要用 ```markdown ``` 包裹
```

### 5.3 关键设计原则

1. **SKILL.md 与 prd-template.md 在 System Prompt 中以原文形式注入**——不允许"概括"，避免规则被简化导致 ai_inferred 标注遗漏。
2. **生成配置（模板/语言/详细度/角色）放在 System Prompt 末尾**——让 LLM 始终基于同一规则，仅调整输出风格。
3. **附件内容按"用户文本 → 附件 1 → 附件 2 ..."固定顺序拼接**——保证多源原料的优先级可预期，工程师无需做智能合并。
4. **附件内容做长度截断**（P1 建议）：单附件超过 50000 字符时截断并标注「（内容过长已截断）」，避免爆 token。

---

## 6. 待确认问题

> 以下问题已合理推断默认值，**需 PM 或最终用户在开发启动前/开发中确认**。工程师可以按"推断默认值"先行实现，遇到需要决策时再回头确认。

| # | 问题 | 推断默认值 | 建议决策方 |
|---|------|-----------|-----------|
| Q1 | **是否需要鉴权？**（API Key、登录态、IP 白名单） | **本期不做鉴权**，假设部署在内网或前台有独立鉴权层 | PM + 部署负责人 |
| Q2 | **并发上限是多少？**（同一时刻允许多少个生成请求） | 暂不限流，依赖 LLM 厂商侧限流；P2 加入令牌桶 | 运维 + PM |
| Q3 | **文件大小限制是否与前台保持一致（20MB）？** | 是，后端不放松也不收紧 | PM（确认无特殊场景） |
| Q4 | **是否支持多文件合并？**（上传 N 个文件如何处理） | **支持**，按"用户文本 → 附件 1 → 附件 2 ..."顺序拼接送入 LLM | PM |
| Q5 | **LLM 厂商选型**（OpenAI / Claude / DeepSeek / Qwen / 国产合规模型？） | **OpenAI 兼容协议** 抽象层，**至少实现 1 个 Provider**（推荐先 OpenAI 或 DeepSeek），Key 稍后注入 | 用户（提供 Key） |
| Q6 | **默认生成超时时间**（整体 90s？首 token 15s？） | 整体 90s / 首 token 15s，通过环境变量可调 | PM |
| Q7 | **`feature_name` 留空时如何处理？** | LLM 自行从原料推断标题 | PM |
| Q8 | **是否需要持久化任何用户数据**（生成历史、用户上传文件）？ | **不做持久化**，无数据库；用户上传文件解析后即丢弃 | PM + 隐私合规 |
| Q9 | **是否对生成内容做敏感词/合规过滤？** | 本期不做；P2 考虑 | 合规负责人 |
| Q10 | **bilingual（中英双语）输出的具体形式？** | 推断：每个小节标题用 `中 / En` 并列，正文以中文为主、关键术语附英文 | PM 确认 |
| Q11 | **`role` 字段对生成结果的影响**（"产品经理"和"开发人员"看到的 PRD 差异有多大？） | 推断：调整术语密度、§3 用户故事详略、§6 技术约束详略；不改变结构 | PM 确认 |
| Q12 | **失败时是否要支持自动重试？**（如 timeout 自动重试 1 次） | 推断：**不自动重试**，由前台根据 `retryable` 字段决定是否提示用户点重试 | PM |

---

## 7. 附录：与前台 `index.html` 的契约对接

> 此节给工程师做联调时参考，不是新需求。

| 前台字段 | 后端字段 | 备注 |
|---------|---------|------|
| `mainInput.value` | `text` | 文本框内容 |
| `uploadedFiles` | `files` | 多个 File 对象 |
| `templateSelect.value` | `template` | 4 个枚举值 |
| `languageSelect.value` | `language` | 3 个枚举值 |
| `detailSelect.value` | `detail` | 4 个枚举值 |
| `roleSelect.value` | `role` | 4 个枚举值 |
| 按钮禁用 + spinner | `start` / `progress` 事件 | 前台在收到 `start` 后禁用按钮 |
| `resultContent.textContent` 累加 | `chunk` 事件 `delta` | 逐 chunk append |
| `copyBtn` / `downloadBtn` 显示 | `done` 事件 | 收到 `done` 后显示 |
| `showToast('error', ...)` | `error` 事件 | 收到 `error` 后停止 spinner 并 Toast |

**前台现有 20MB 校验逻辑**（`index.html:1092`）保留作为前端体验保护，**不依赖** 后端做硬限制但后端必须兜底拒绝。

---

## 变更历史

| 日期 | 版本 | 变更摘要 | PM |
|------|------|---------|-----|
| 2025-01-XX | 1.0 | 初版：后台生成服务简单 PRD | Alice（产品经理） |
