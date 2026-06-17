# AI PRD Platform

> 将任意形态的 PRD（草稿、大纲、混杂的 UI 描述……）一键规整为符合 `prd-template.md` 标准的结构化 PRD 文档，并支持流式生成。

## 项目结构

```
AI_PRD_Platform/
├── index.html                       # 单文件前端：上传 / 流式渲染 / 导出
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

### 后端

```bash
cd prd-forge-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 填入 LLM_API_KEY
uvicorn app.main:app --reload --port 8000
```

### 前端

直接用浏览器打开 `index.html`（或起静态服务器），配置后端地址即可。

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

## License

MIT
