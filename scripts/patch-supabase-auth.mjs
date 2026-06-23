#!/usr/bin/env node
/**
 * 仅修补 Supabase Auth：Site URL、邮件模板（含验证码）、邮箱确认开关
 *
 * 用法：
 *   cp .env.supabase.example .env.supabase  # 若尚未创建
 *   # 填入 SUPABASE_URL、SUPABASE_ACCESS_TOKEN
 *   node scripts/patch-supabase-auth.mjs
 */

import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

function loadEnv(filePath) {
  if (!existsSync(filePath)) return {};
  const env = {};
  for (const line of readFileSync(filePath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    env[key] = val;
  }
  return env;
}

function projectRefFromUrl(url) {
  const m = url.match(/https:\/\/([^.]+)\.supabase\.co/);
  return m ? m[1] : null;
}

async function apiFetch(token, path, options = {}) {
  const res = await fetch(`https://api.supabase.com/v1${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let body;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!res.ok) {
    const msg = typeof body === 'object' ? (body.message || JSON.stringify(body)) : body;
    throw new Error(`API ${path} → ${res.status}: ${msg}`);
  }
  return body;
}

async function main() {
  const envPath = join(ROOT, '.env.supabase');
  const env = loadEnv(envPath);
  const url = env.SUPABASE_URL;
  const token = env.SUPABASE_ACCESS_TOKEN;
  const projectRef = env.SUPABASE_PROJECT_REF || projectRefFromUrl(url);
  const siteUrl = env.SUPABASE_SITE_URL || 'https://driftmrd.github.io/AI_PRD_Platform/login.html';
  const redirectUrls = env.SUPABASE_REDIRECT_URLS ||
    'https://driftmrd.github.io/AI_PRD_Platform/**,http://localhost:5173/**,http://127.0.0.1:5173/**';

  if (!url || !token || !projectRef) {
    console.error('❌ 请在 .env.supabase 中配置 SUPABASE_URL、SUPABASE_ACCESS_TOKEN');
    process.exit(1);
  }

  console.log(`修补 Auth 配置 → 项目 ${projectRef}`);
  console.log(`  Site URL: ${siteUrl}`);

  const urlOnlyBody = {
    external_email_enabled: true,
    mailer_autoconfirm: false,
    site_url: siteUrl,
    uri_allow_list: redirectUrls,
  };

  const fullBody = {
    ...urlOnlyBody,
    mailer_subjects_confirmation: 'PRD Forge 注册验证码',
    mailer_templates_confirmation_content:
      '<h2>PRD Forge 注册验证</h2>' +
      '<p>您的验证码是：<strong>{{ .Token }}</strong></p>' +
      '<p>验证码有效期约 1 小时，请在注册页输入。</p>' +
      '<p>或点击链接直接确认：<a href="{{ .ConfirmationURL }}">确认邮箱</a></p>',
  };

  let res = await fetch(`https://api.supabase.com/v1/projects/${projectRef}/config/auth`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(fullBody),
  });

  if (!res.ok) {
    const errText = await res.text();
    const freeTierTemplateBlock = errText.includes('Email template modification is not available');
    if (!freeTierTemplateBlock) {
      throw new Error(`API /projects/${projectRef}/config/auth → ${res.status}: ${errText}`);
    }

    console.log('  ⚠ 免费版默认邮件服务无法通过 API 改模板，仅更新 URL 配置…');
    res = await fetch(`https://api.supabase.com/v1/projects/${projectRef}/config/auth`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(urlOnlyBody),
    });
    if (!res.ok) {
      const retryText = await res.text();
      throw new Error(`API /projects/${projectRef}/config/auth → ${res.status}: ${retryText}`);
    }

    console.log('✅ 已更新：Site URL、Redirect URLs、邮箱确认开关');
    console.log('');
    console.log('⚠ 验证码邮件模板需在 Dashboard 手动修改（免费版限制）：');
    console.log('   Authentication → Email Templates → Confirm signup');
    console.log('   正文加入：{{ .Token }}');
    return;
  }

  console.log('✅ 已更新：Site URL、Redirect URLs、确认邮件模板（含 6 位验证码）');
  console.log('   请重新注册一次测试；旧邮件里的 localhost 链接已失效。');
}

main().catch((err) => {
  console.error('❌', err.message);
  process.exit(1);
});
