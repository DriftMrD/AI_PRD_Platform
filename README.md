# AI PRD Platform

> 将任意形态的 PRD（草稿、大纲、混杂的 UI 描述……）一键规整为符合 `prd-template.md` 标准的结构化 PRD 文档，并支持流式生成。

## 项目结构

```
AI_PRD_Platform/
├── index.html                       # 单文件前端：上传 / 流式渲染 / 导出
├── workspace.html                   # 工作台：对话 + PRD 预览
├── login.html                       # 登录 / 注册
├── js/
│   ├── supabase-config.js           # Supabase URL + anon key（需自行填写）
│   └── supabase-client.js           # Auth + 会话云端存储
├── supabase/schema.sql              # 数据库建表 + RLS
├── prd-template.md                  # 标准 PRD 模板（生成目标）
├── SKILL.md                         # PRD → 模板的转换规则（载入到 LLM 提示词）
├── docs/
│   ├── ARCHITECTURE.md              # 系统架构
│   └── PRD-backend.md               # 后端需求
└── prd-forge-backend/               # FastAPI 后端
    ├── app/
    │   ├── main.py                  # FastAPI 入口
    │   ├── config.py                # pydantic-settings 配置
    │   ├── errors.py                # 错误码常量
    │   ├── parsers/                 # md/txt/docx/pdf 文件解析
    │   ├── llm/                     # LLM 适配器抽象 + OpenAI-compatible 实现
    │   ├── prompts/                 # 提示词构建器（注入 SKILL + 模板）
    │   ├── models/                  # Pydantic 模型
    │   └── routers/                 # /api/generate
    ├── requirements.txt
    └── .env.example
```

## 快速开始

### 1. 启动后端

```bash
cd prd-forge-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `prd-forge-backend/.env`，填入你的 LLM 配置：

```bash
# DeepSeek（OpenAI 兼容协议，国内直连）
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的-key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 其他 OpenAI 兼容服务（OpenAI / 智谱 / Moonshot / Ollama 等）
# LLN_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

启动：

```bash
uvicorn app.main:app --reload --port 8000
```

健康检查：`curl http://127.0.0.1:8000/` → `{"status":"ok"}`

### 2. 打开前端

直接用浏览器打开 `index.html`，或在仓库根目录起一个静态服务器：

```bash
cd ..  # 回到仓库根
python -m http.server 5173
# 浏览器访问 http://localhost:5173/
```

**默认行为**：

| 访问方式 | 后端地址 | 说明 |
|---|---|---|
| `http://localhost:5173/` | `http://localhost:8000` | 自动检测 localhost，连本地后端 |
| `http://127.0.0.1:5173/` | `http://127.0.0.1:8000` | 同上 |
| GitHub Pages (`driftmrd.github.io/...`) | mock 模式 | 默认走假数据演示 |

**显式指定后端地址**（推荐用于 GitHub Pages）：

```
https://driftmrd.github.io/AI_PRD_Platform/?api=https://your-backend.example.com
```

只要后端 `CORS_ORIGINS` 里包含 `https://driftmrd.github.io` 即可跨域。

### 3. 配置 Supabase（用户登录 + 历史云端存储）

**一键配置（推荐）**：

```bash
cp .env.supabase.example .env.supabase
# 编辑 .env.supabase，填入 URL、anon key、Access Token（见下方说明）
node scripts/setup-supabase.mjs
```

Access Token 获取：Supabase Dashboard → 右上角头像 → **Account** → **Access Tokens** → Generate。

手动步骤见 **[docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md)**。

配置完成后：
- 未登录用户无法生成 PRD（会跳转登录页）
- 历史对话保存在 Supabase，按账号隔离
- 旧版 localStorage 历史会在首次登录时自动迁移

## 技术栈

- **后端**：FastAPI 0.110+ · Uvicorn · SSE 流式响应 · pydantic v2
- **LLM**：OpenAI-compatible 协议（可切换 provider）
- **文件解析**：python-docx · pypdf
- **前端**：原生 HTML + Vanilla JS + EventSource（SSE）

## 核心特性

- 多文件上传（md / txt / docx / pdf），单文件上限 20MB / 50K 字符
- 流式生成（SSE），前端实时追加渲染
- 5 种事件：`start` / `progress` / `chunk` / `done` / `error`
- 客户端断开自动取消 LLM 流
- 模板与 SKILL 启动期注入，请求时无 I/O

## 文档

- 架构设计：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 后端需求：[docs/PRD-backend.md](docs/PRD-backend.md)
- PRD 模板：[prd-template.md](prd-template.md)
- 转换规则：[SKILL.md](SKILL.md)
- **线上部署**：[DEPLOY.md](DEPLOY.md) ← 后端到 Render + key 安全注入

## License

MIT
