# 部署指南：把后端安全放到公网

> 目标：前端 (GitHub Pages) + 后端 (Render) + key 永远只在后端环境变量里

## 架构

```
浏览器
  │
  │  HTTPS GET /
  │  HTTPS POST /api/generate (multipart + SSE)
  │
  ▼
GitHub Pages (driftmrd.github.io)         ← 只有静态文件，没 key
  │
  │  ?api=https://xxx.onrender.com
  │
  ▼
Render (后端 FastAPI)                     ← LLM_API_KEY 在这里！
  │
  │  https://api.deepseek.com/v1/chat/completions
  │  Authorization: Bearer sk-xxx           ← 转发调用
  │
  ▼
DeepSeek / OpenAI / 其他 LLM
```

**关键安全边界**：key 只存在于 Render Dashboard 的 Environment Secret 里。浏览器抓包只能看到 `?api=...`，看不到后端 → DeepSeek 之间的 Authorization 头。

## 一、注册 Render（一次性）

1. 打开 https://render.com → Sign Up → 用 **GitHub 账号**登录（方便自动连接仓库）
2. 免费层需绑卡（不会扣费，只是防滥用）

## 二、用 Blueprint 一键部署

1. Render Dashboard → **New** → **Blueprint**
2. **Connect repository** → 选 `DriftMrD/AI_PRD_Platform`
3. Render 自动读 `render.yaml` → 显示一个 web service `prd-forge-backend`
4. 点 **Apply** → 开始 build（~2 分钟）

## 三、注入 LLM_API_KEY（关键！）

部署成功后服务会一直 crash（启动期 `LLM_API_KEY` 缺失），正常：

1. Dashboard → `prd-forge-backend` → 左侧 **Environment**
2. **Add Secret**：
   - **Key**: `LLM_API_KEY`
   - **Value**: `sk-你的新key`（仅填在 Render Dashboard，不要写进代码或文档）
3. 点 **Save Changes** → Render 自动 redeploy
4. 等 1-2 分钟，看日志出现 `startup: settings loaded (provider=openai, model=deepseek-chat)` 就算成功

## 四、拿到后端域名

Dashboard → `prd-forge-backend` → 顶部有 `https://prd-forge-backend-xxx.onrender.com`

测试：
```bash
curl https://prd-forge-backend-xxx.onrender.com/
# 期望：{"status":"ok"}
```

> **冷启动注意**：免费层 15 分钟无请求会 sleep，下次访问需要 30-50 秒唤醒。生产环境可以绑卡升 Starter ($7/月) 保持常驻。

## 五、接前端

打开：
```
https://driftmrd.github.io/AI_PRD_Platform/?api=https://prd-forge-backend-xxx.onrender.com
```

`?api=` 把后端地址注入前端，前端 fetch 直接调 Render。

也可以**永久写入前端默认**（不想每次手敲）：

编辑 `index.html` 第 1166 行附近：
```js
if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
  return 'http://localhost:8000';
}
return 'https://prd-forge-backend-xxx.onrender.com';   // ← 改这里
```

## 六、安全自检

部署完跑一遍这些，确认没漏：

```bash
# 1) Pages 源码里不应该有 key
curl -s https://driftmrd.github.io/AI_PRD_Platform/ | grep -E 'sk-' | head
# 期望：无输出

# 2) Render 环境变量在 Dashboard 看，前端拿不到
# 浏览器 DevTools → Network → 看 /api/generate 请求：
#   - 看不到 Authorization 头（正确，那是后端→DeepSeek 之间的）
#   - 看不到 LLM_API_KEY 字样（正确）

# 3) .env 不会进 git
cd AI_PRD_Platform
git log --all --full-history -- prd-forge-backend/.env
# 期望：fatal: ambiguous argument（说明从来没进过 git）
```

## 七、备选方案

| 平台 | 优点 | 缺点 |
|---|---|---|
| **Render** | 免费层稳，GitHub 集成好 | 冷启动慢（免费层 sleep） |
| Railway | 一直热，速度快 | $5/月免费额度 |
| Cloudflare Workers | 隐藏 DeepSeek 真实 endpoint，超快 | 需改写后端为 Worker 格式 |
| Fly.io | 性能好 | 配置稍复杂 |

## 八、Key 泄露应急

如果怀疑 key 泄露了（截图、commit、群消息……）：

1. **立即去 DeepSeek Console 撤销/重置 key**：https://platform.deepseek.com/api_keys → Revoke → 新建一个
2. Render Dashboard → Environment → 替换 `LLM_API_KEY` → Save
3. 删掉 git 历史里可能的 key 痕迹：`git filter-repo --invert-paths --path prd-forge-backend/.env`（如果之前误提交过）
