# Supabase 用户系统配置指南

PRD Forge 使用 Supabase 提供：

- **用户登录/注册**（邮箱 + 密码）
- **历史对话云端存储**（按用户隔离，RLS 保护）
- **跨设备同步**（同一账号任意浏览器可访问）

后端 FastAPI **仍只负责 PRD 生成**，不存用户数据；会话数据存在 Supabase Postgres。

---

## 一、注册 Supabase（免费）

1. 打开 https://supabase.com → **Start your project**
2. 用 GitHub 登录
3. **New project**：
   - Name: `prd-forge`（随意）
   - Database Password: 设一个强密码（保存好，很少用到）
   - Region: 选离用户最近的（如 `Northeast Asia (Tokyo)`）
4. 等 1–2 分钟项目创建完成

---

## 二、一键配置（推荐）

如果你不想手动点 SQL Editor，可以用脚本自动完成 **步骤 2 / 3 / 4 / 5**：

### 需要准备的 3 个值

| 变量 | 从哪里复制 |
|------|-----------|
| `SUPABASE_URL` | **Project URL**（只要域名，不要 `/rest/v1/`）<br>例：`https://vxcxaiylcjrcukgyfath.supabase.co` |
| `SUPABASE_ANON_KEY` | **Publishable key**（`sb_publishable_...`）或旧版 **anon public**（`eyJ...`） |
| `SUPABASE_ACCESS_TOKEN` | 右上角头像 → **Account** → **Access Tokens** → Generate |

### 运行

```bash
cp .env.supabase.example .env.supabase
# 用编辑器打开 .env.supabase，填入上面 3 个值
node scripts/setup-supabase.mjs
```

脚本会自动：
1. 执行 `supabase/schema.sql` 建表
2. 开启邮箱登录 + 关闭注册确认邮件
3. 写入 `js/supabase-config.js`
4. 设置 Site URL 和 Redirect URLs

---

## 二（手动）、创建数据表

1. 左侧 **SQL Editor** → **New query**
2. 复制仓库 `supabase/schema.sql` 的全部内容，粘贴并 **Run**
3. 成功后会创建 `prd_sessions` 表及 Row Level Security 策略

---

## 三、开启邮箱登录

1. 左侧 **Authentication** → **Providers**
2. 确认 **Email** 已启用（默认开启）
3. （可选）**Authentication** → **Settings**：
   - 开发阶段可关闭 **Confirm email**，注册后无需收邮件即可登录
   - 正式上线建议开启邮箱验证

---

## 四、配置前端

1. 左侧 **Project Settings** → **API**
2. 复制：
   - **Project URL**（如 `https://xxxxx.supabase.co`）
   - **anon public** key（`eyJ...` 开头）

3. 编辑仓库 `js/supabase-config.js`：

```javascript
window.PRD_FORGE_SUPABASE = {
  url: 'https://你的项目.supabase.co',
  anonKey: '你的 anon key'
};
```

> `anon key` 可以放在前端（公开），数据安全由 RLS 保证；**不要**把 `service_role` key 放进前端。

---

## 五、配置站点 URL（重要）

Supabase 需要知道你的前端域名，否则登录回调可能异常。

1. **Authentication** → **URL Configuration**
2. **Site URL** 设为你的前端地址，例如：
   - 本地：`http://localhost:5173`
   - GitHub Pages：`https://driftmrd.github.io/AI_PRD_Platform/`
3. **Redirect URLs** 添加（可多行）：
   ```
   http://localhost:5173/**
   http://127.0.0.1:5173/**
   https://driftmrd.github.io/AI_PRD_Platform/**
   ```

---

## 六、本地验证

```bash
# 仓库根目录
python -m http.server 5173
```

1. 浏览器打开 http://localhost:5173/login.html
2. 注册账号 → 登录
3. 首页输入需求 → **生成 PRD 文档**
4. 刷新页面 → **历史记录** 应能看到刚才的会话

---

## 七、从 localStorage 迁移

首次登录后，工作台会自动把浏览器里旧的 `prd_forge_sessions`（localStorage）迁移到 Supabase，并清除本地副本。

---

## 八、数据模型

| 字段 | 说明 |
|------|------|
| `id` | UUID，会话 ID |
| `user_id` | 关联 `auth.users` |
| `title` | 会话标题（取首条需求前 24 字） |
| `config` | 模板/语言/详细度/角色 |
| `files` | 上传文件元数据 + base64 |
| `messages` | 对话消息数组 |
| `prd` | 生成的 PRD 正文 |
| `status` | `pending` / `generating` / `done` / `error` |

---

## 九、常见问题

**Q: 登录后提示「加载历史失败」**  
A: 检查是否已执行 `supabase/schema.sql`，以及 `js/supabase-config.js` 是否填对。

**Q: 注册后无法登录**  
A: 若开启了邮箱验证，需先点确认邮件里的链接；或在 Supabase 关闭 Confirm email。

**Q: 免费版够用吗？**  
A: 个人/小团队完全够用（50K MAU、500MB 数据库）。注意 7 天无访问项目会暂停，Dashboard 里点 Resume 即可。

**Q: 想用 Google 登录？**  
A: Authentication → Providers → Google，按文档配置 OAuth Client ID。前端可后续加 `signInWithOAuth` 按钮。

---

## 十、文件清单

```
js/supabase-config.js      ← 填入 URL + anon key（你已配置）
js/supabase-config.example.js
js/supabase-client.js      ← Auth + SessionStore
login.html                 ← 登录/注册页
supabase/schema.sql        ← 数据库建表脚本
```
