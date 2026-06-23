/**
 * 飞书 / 传神分享：选人后直接发送 MD 文件或消息卡片。
 * - 飞书 WebView 内：JSAPI sendMessageCard（原生选人 + 卡片消息）
 * - 桌面浏览器：调用后端 lark-cli 搜索联系人 + 上传文件 + 发送
 * - 兜底：剪贴板 + 手动粘贴
 */
const PrdForgeFeishu = (() => {
  const SDK_URL =
    'https://lf1-cdn-tos.bytegoofy.com/goofy/lark/op/h5-js-sdk/h5-js-sdk-1.5.23.js';
  const RELAY_PAGE = 'feishu-share.html';
  const MAX_CARD_CHARS = 12000;

  let sdkReady = false;
  let sdkInitPromise = null;
  /** 用户通过回调注册的桌面版分享对话框控制 */
  let _browserShareDialog = null;

  function isFeishuEnv() {
    const ua = navigator.userAgent || '';
    return (
      /Lark|Feishu|Chuanshen|传神/i.test(ua) ||
      typeof window.tt !== 'undefined' ||
      typeof window.h5sdk !== 'undefined'
    );
  }

  /* ---------- 桌面浏览器分享对话框注册 ---------- */
  function registerBrowserDialog(dialogCallbacks) {
    _browserShareDialog = dialogCallbacks;
  }

  /* ---------- 桌面浏览器：搜索联系人 ---------- */
  async function searchContacts(apiBase, query) {
    const res = await fetch(apiBase + '/api/feishu/search-contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '搜索失败');
    }
    return res.json();
  }

  /* ---------- 桌面浏览器：发送 MD 文件 ---------- */
  async function sendFileViaCli(apiBase, content, title, versionLabel, openId) {
    const res = await fetch(apiBase + '/api/feishu/share-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        title,
        version_label: versionLabel,
        recipient_open_id: openId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '发送失败');
    }
    return res.json();
  }

  /* ---------- SDK 初始化 ---------- */
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector('script[src="' + src + '"]')) {
        resolve();
        return;
      }
      const s = document.createElement('script');
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('飞书 SDK 加载失败'));
      document.head.appendChild(s);
    });
  }

  async function ensureSdk(apiBase) {
    if (sdkReady) return true;
    if (!isFeishuEnv()) return false;
    if (sdkInitPromise) return sdkInitPromise;

    sdkInitPromise = (async () => {
      try {
        await loadScript(SDK_URL);
      } catch {
        return false;
      }

      const pageUrl = location.href.split('#')[0];
      let res;
      try {
        res = await fetch(
          apiBase +
            '/api/feishu/jssdk-config?url=' +
            encodeURIComponent(pageUrl)
        );
      } catch {
        return false;
      }
      if (!res.ok) return false;

      const cfg = await res.json();
      if (!cfg.enabled) return false;

      return new Promise((resolve) => {
        window.h5sdk.config({
          appId: cfg.appId,
          timestamp: cfg.timestamp,
          nonceStr: cfg.nonceStr,
          signature: cfg.signature,
          jsApiList: ['sendMessageCard', 'setClipboardData'],
          onSuccess: () => {
            sdkReady = true;
            resolve(true);
          },
          onFail: () => resolve(false),
        });
      });
    })();

    return sdkInitPromise;
  }

  function buildCardContent(title, markdown) {
    let body = markdown;
    if (body.length > MAX_CARD_CHARS) {
      body =
        body.slice(0, MAX_CARD_CHARS) +
        '\n\n…（内容过长已截断，请在工作台查看完整版）';
    }
    return {
      msg_type: 'interactive',
      card: {
        schema: '2.0',
        header: {
          title: { tag: 'plain_text', content: title },
        },
        body: {
          elements: [{ tag: 'markdown', content: body }],
        },
      },
    };
  }

  function buildShareRelayUrl(shareId) {
    const url = new URL(RELAY_PAGE, location.href);
    const api = new URLSearchParams(location.search).get('api');
    if (api) url.searchParams.set('api', api);
    url.searchParams.set('feishu_share', '1');
    url.searchParams.set('share_id', shareId);
    return url.href.split('#')[0];
  }

  function openInFeishuWebview(shareId) {
    const target = buildShareRelayUrl(shareId);
    const applink =
      'https://applink.feishu.cn/client/web_url/open?mode=window&url=' +
      encodeURIComponent(target);
    const a = document.createElement('a');
    a.href = applink;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function createSharePayload(apiBase, shareText, title) {
    const res = await fetch(apiBase + '/api/feishu/share-payload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: shareText, title }),
    });
    if (!res.ok) {
      throw new Error('暂存分享内容失败');
    }
    const data = await res.json();
    if (!data.shareId) {
      throw new Error('无效的服务端响应');
    }
    return data.shareId;
  }

  async function fetchSharePayload(apiBase, shareId) {
    const res = await fetch(
      apiBase + '/api/feishu/share-payload/' + encodeURIComponent(shareId)
    );
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.text) return null;
    return { text: data.text, title: data.title || 'PRD 文档' };
  }

  function sendShareCard(shareText, title, vLabel, onToast) {
    const cardContent = buildCardContent(title, shareText);
    const run = () => {
      window.tt.sendMessageCard({
        shouldChooseChat: true,
        chooseChatParams: {
          allowCreateGroup: false,
          multiSelect: false,
          selectType: 2,
          confirmTitle: '发送 PRD',
          confirmDesc: '确认发送给所选联系人？',
          externalChat: true,
        },
        cardContent,
        success: () => onToast('已发送 ' + vLabel, 'success'),
        fail: (res) => {
          const msg =
            (res && (res.errMsg || res.errString)) || '发送失败，请重试';
          onToast(msg, 'error');
        },
      });
    };

    if (window.h5sdk && typeof window.h5sdk.ready === 'function') {
      window.h5sdk.ready(run);
    } else if (window.tt) {
      run();
    }
  }

  async function shareWithCard(apiBase, shareText, title, vLabel, onToast) {
    if (isFeishuEnv()) {
      const ready = await ensureSdk(apiBase);
      if (ready) {
        sendShareCard(shareText, title, vLabel, onToast);
        return;
      }
      try {
        await navigator.clipboard.writeText(shareText);
      } catch {
        onToast('发送失败且无法复制，请手动复制', 'error');
        return;
      }
      onToast(
        '后端未配置飞书应用，已复制到剪贴板，请手动发送',
        'success'
      );
      return;
    }

    let shareId;
    try {
      shareId = await createSharePayload(apiBase, shareText, title);
    } catch (e) {
      onToast('分享失败：' + e.message, 'error');
      return;
    }
    onToast('正在飞书内打开选人…', 'success');
    openInFeishuWebview(shareId);
  }

  async function share(apiBase, shareText, meta, onToast) {
    const title = meta?.title || 'PRD 文档';
    const vLabel = meta?.vLabel || '';

    // 飞书 WebView → JSAPI 原生选人 + 卡片
    if (isFeishuEnv()) {
      await shareWithCard(apiBase, shareText, title, vLabel, onToast);
      return;
    }

    // 桌面浏览器 → lark-cli 后端搜索联系人 + 发送 MD 文件
    if (_browserShareDialog && _browserShareDialog.open) {
      _browserShareDialog.open({
        apiBase,
        shareText,
        title,
        vLabel,
        onToast,
      });
      return;
    }

    // 兜底：剪贴板
    try {
      await navigator.clipboard.writeText(shareText);
      onToast('已复制到剪贴板，请手动粘贴发送', 'success');
    } catch {
      onToast('复制失败，请手动复制内容', 'error');
    }
  }

  /** feishu-share.html 中转页：通过 URL 中的 share_id 拉取内容并唤起选人 */
  async function runRelayShare(apiBase, onStatus) {
    const params = new URLSearchParams(location.search);
    if (params.get('feishu_share') !== '1') return false;

    const shareId = params.get('share_id');
    if (!shareId) {
      onStatus('分享链接无效，请返回工作台重新点击分享', true);
      return false;
    }

    onStatus('正在加载分享内容…');
    const pending = await fetchSharePayload(apiBase, shareId);
    if (!pending) {
      onStatus('分享内容已过期，请返回工作台重新点击分享', true);
      return false;
    }

    onStatus('正在连接飞书…');
    const ready = await ensureSdk(apiBase);
    if (ready) {
      onStatus('请选择要发送的联系人…');
      sendShareCard(pending.text, pending.title, pending.title, onStatus);
      return true;
    }

    try {
      await navigator.clipboard.writeText(pending.text);
      onStatus('飞书应用未配置，内容已复制到剪贴板，请手动发送', true);
    } catch {
      onStatus('飞书未就绪，请返回工作台重试', true);
    }
    return true;
  }

  return {
    share,
    runRelayShare,
    isFeishuEnv,
    searchContacts,
    sendFileViaCli,
    registerBrowserDialog,
  };
})();
