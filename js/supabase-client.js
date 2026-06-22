(function () {
  'use strict';

  const STORAGE_KEY = 'prd_forge_sessions';

  window.PrdForge = window.PrdForge || {};

  PrdForge.isConfigured = function () {
    const cfg = window.PRD_FORGE_SUPABASE;
    if (!cfg || !cfg.url || !cfg.anonKey) return false;
    if (cfg.url.includes('YOUR_') || cfg.anonKey.includes('YOUR_')) return false;
    return true;
  };

  PrdForge.getSupabase = function () {
    if (!PrdForge.isConfigured()) return null;
    if (!PrdForge._client) {
      PrdForge._client = supabase.createClient(
        window.PRD_FORGE_SUPABASE.url,
        window.PRD_FORGE_SUPABASE.anonKey
      );
    }
    return PrdForge._client;
  };

  PrdForge.getSession = async function () {
    const sb = PrdForge.getSupabase();
    if (!sb) return null;
    const { data } = await sb.auth.getSession();
    return data.session;
  };

  PrdForge.requireAuth = async function () {
    if (!PrdForge.isConfigured()) {
      PrdForge.redirectToSetup();
      return null;
    }
    const session = await PrdForge.getSession();
    if (!session) {
      const redirect = encodeURIComponent(location.pathname.split('/').pop() + location.search);
      location.href = 'login.html?redirect=' + redirect;
      return null;
    }
    return session;
  };

  PrdForge.redirectToSetup = function () {
    location.href = 'login.html?setup=1';
  };

  PrdForge.signOut = async function () {
    const sb = PrdForge.getSupabase();
    if (sb) await sb.auth.signOut();
    const returnTo = encodeURIComponent('index.html' + (location.search || ''));
    location.href = 'login.html?redirect=' + returnTo;
  };

  PrdForge.renderAuthHeader = async function (containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;

    if (!PrdForge.isConfigured()) {
      el.innerHTML = '<a href="login.html?setup=1" class="auth-link">配置 Supabase</a>';
      return;
    }

    const session = await PrdForge.getSession();
    if (!session) {
      const returnTo = encodeURIComponent(location.pathname.split('/').pop() + location.search);
      const loginHref = 'login.html?redirect=' + returnTo;
      el.innerHTML = '<a href="' + loginHref + '" class="auth-link" id="headerLoginLink">登录</a>';
      document.getElementById('headerLoginLink')?.addEventListener('click', async (e) => {
        if (typeof window.saveDraftBeforeLogin === 'function') {
          e.preventDefault();
          try { await window.saveDraftBeforeLogin(); } catch { /* ignore */ }
          location.href = loginHref;
        }
      });
      return;
    }

    const email = session.user.email || '已登录';
    el.innerHTML =
      '<span class="auth-email" title="' + escapeAttr(email) + '">' + escapeHtml(email) + '</span>' +
      '<button type="button" class="auth-btn" id="logoutBtn">退出</button>';
    document.getElementById('logoutBtn')?.addEventListener('click', () => PrdForge.signOut());
  };

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  PrdForge.SessionStore = {
    rowToSession(row) {
      const session = {
        id: row.id,
        title: row.title,
        createdAt: new Date(row.created_at).getTime(),
        updatedAt: new Date(row.updated_at).getTime(),
        config: row.config || {},
        files: row.files || [],
        messages: row.messages || [],
        prd: row.prd || '',
        prdVersions: row.prd_versions || [],
        status: row.status || 'pending'
      };
      if (!session.prdVersions.length && session.prd) {
        session.prdVersions = [{ v: 1, content: session.prd, createdAt: session.updatedAt, label: 'v1' }];
      }
      return session;
    },

    sessionToRow(session, userId) {
      return {
        id: session.id,
        user_id: userId,
        title: session.title || '新需求',
        config: session.config || {},
        files: session.files || [],
        messages: session.messages || [],
        prd: session.prd || '',
        prd_versions: session.prdVersions || [],
        status: session.status || 'pending',
        deleted: 0
      };
    },

    async loadAll() {
      const sb = PrdForge.getSupabase();
      const { data: { user } } = await sb.auth.getUser();
      if (!user) return [];

      const { data, error } = await sb
        .from('prd_sessions')
        .select('*')
        .eq('deleted', 0)
        .order('updated_at', { ascending: false })
        .limit(50);

      if (error) throw new Error(error.message);
      return (data || []).map(PrdForge.SessionStore.rowToSession);
    },

    async save(session) {
      const sb = PrdForge.getSupabase();
      const { data: { user } } = await sb.auth.getUser();
      if (!user) throw new Error('未登录');

      const row = PrdForge.SessionStore.sessionToRow(session, user.id);
      const { error } = await sb.from('prd_sessions').upsert(row, { onConflict: 'id' });
      if (error) throw new Error(error.message);
    },

    async remove(sessionId) {
      const sb = PrdForge.getSupabase();
      const { data: { user } } = await sb.auth.getUser();
      if (!user) throw new Error('未登录');

      const { error } = await sb
        .from('prd_sessions')
        .update({ deleted: 1 })
        .eq('id', sessionId);
      if (error) throw new Error(error.message);
    },

    async create(pending) {
      const sb = PrdForge.getSupabase();
      const { data: { user } } = await sb.auth.getUser();
      if (!user) throw new Error('未登录');

      const title = (pending.text || '').trim().slice(0, 24) || '新需求';
      const row = {
        user_id: user.id,
        title,
        config: {
          template: pending.template,
          language: pending.language,
          detail: pending.detail,
          role: pending.role
        },
        files: pending.files || [],
        messages: [{ role: 'user', content: pending.text, time: Date.now() }],
        prd: '',
        prd_versions: [],
        status: 'pending',
        deleted: 0
      };

      const { data, error } = await sb.from('prd_sessions').insert(row).select().single();
      if (error) throw new Error(error.message);

      const session = PrdForge.SessionStore.rowToSession(data);
      session.autoStart = true;
      return session;
    },

    async migrateLocalSessions() {
      let local = [];
      try {
        local = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      } catch {
        return 0;
      }
      if (!local.length) return 0;

      const sb = PrdForge.getSupabase();
      const { data: { user } } = await sb.auth.getUser();
      if (!user) return 0;

      const rows = local.slice(0, 50).map(s => ({
        user_id: user.id,
        title: s.title || '新需求',
        config: s.config || {},
        files: s.files || [],
        messages: s.messages || [],
        prd: s.prd || '',
        prd_versions: s.prdVersions || [],
        status: s.status === 'generating' ? 'error' : (s.status || 'done'),
        deleted: 0,
        created_at: s.createdAt ? new Date(s.createdAt).toISOString() : undefined,
        updated_at: s.updatedAt ? new Date(s.updatedAt).toISOString() : undefined
      }));

      const { error } = await sb.from('prd_sessions').insert(rows);
      if (error) throw new Error(error.message);

      localStorage.removeItem(STORAGE_KEY);
      return rows.length;
    }
  };
})();
