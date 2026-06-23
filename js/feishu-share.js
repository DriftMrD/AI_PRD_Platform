/**
 * 飞书 / 传神分享：选人后直接发送 Markdown 消息卡片（无需粘贴）。
 */
const PrdForgeFeishu = (() => {
  const SDK_URL =
    'https://lf1-cdn-tos.bytegoofy.com/goofy/lark/op/h5-js-sdk/h5-js-sdk-1.5.23.js';
  const PENDING_KEY = 'prd_feishu_share_pending';
  const TEXT_KEY = 'prd_feishu_share_text';
  const TITLE_KEY = 'prd_feishu_share_title';
  /** 飞书卡片 Markdown 有长度上限，超出则截断 */
  const MAX_CARD_CHARS = 12000;

  let sdkReady = false;
  let sdkInitPromise = null;

  function isFeishuEnv() {
    return (
      /Lark|Feishu/i.test(navigator.userAgent) ||
      typeof window.tt !== 'undefined'
    );
  }

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

  function openInFeishuWebview(shareIntent) {
    const url = new URL(location.href);
    if (shareIntent) url.searchParams.set('feishu_share', '1');
    const target = url.href.split('#')[0];
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

  function stashPendingShare(shareText, title) {
    localStorage.setItem(PENDING_KEY, '1');
    localStorage.setItem(TEXT_KEY, shareText);
    localStorage.setItem(TITLE_KEY, title);
  }

  function readPendingShare() {
    if (localStorage.getItem(PENDING_KEY) !== '1') return null;
    const text = localStorage.getItem(TEXT_KEY);
    const title = localStorage.getItem(TITLE_KEY);
    localStorage.removeItem(PENDING_KEY);
    localStorage.removeItem(TEXT_KEY);
    localStorage.removeItem(TITLE_KEY);
    if (!text) return null;
    return { text, title: title || 'PRD 文档' };
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

    stashPendingShare(shareText, title);
    onToast('正在飞书内打开，选人后即可发送…', 'success');
    openInFeishuWebview(true);
  }

  async function share(apiBase, shareText, meta, onToast) {
    const title = meta?.title || 'PRD 文档';
    const vLabel = meta?.vLabel || '';
    await shareWithCard(apiBase, shareText, title, vLabel, onToast);
  }

  async function maybeAutoShare(apiBase, onToast) {
    const params = new URLSearchParams(location.search);
    if (params.get('feishu_share') !== '1') return;

    params.delete('feishu_share');
    const clean =
      location.pathname + (params.toString() ? '?' + params.toString() : '');
    history.replaceState(null, '', clean);

    const pending = readPendingShare();
    if (!pending) return;

    const ready = await ensureSdk(apiBase);
    if (ready) {
      sendShareCard(pending.text, pending.title, pending.title, onToast);
      return;
    }
    try {
      await navigator.clipboard.writeText(pending.text);
      onToast('飞书未就绪，已复制到剪贴板，请手动发送', 'success');
    } catch {
      onToast('飞书未就绪，请重新点击分享', 'error');
    }
  }

  return { share, maybeAutoShare, isFeishuEnv };
})();
