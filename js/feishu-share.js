/**
 * 飞书 / 传神分享：飞书内 chooseChat 选人；外部浏览器先复制再打开飞书内页面。
 */
const PrdForgeFeishu = (() => {
  const SDK_URL =
    'https://lf1-cdn-tos.bytegoofy.com/goofy/lark/op/h5-js-sdk/h5-js-sdk-1.5.23.js';
  const PENDING_KEY = 'prd_feishu_share_pending';

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
          jsApiList: ['chooseChat', 'setClipboardData'],
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

  function chooseChat(vLabel, onToast) {
    const run = () => {
      window.tt.chooseChat({
        allowCreateGroup: false,
        multiSelect: false,
        selectType: 2,
        confirmTitle: '分享给',
        confirmDesc:
          '内容已复制到剪贴板，可在留言框粘贴（Ctrl+V / ⌘V）后发送',
        showMessageInput: true,
        externalChat: true,
        success: () => onToast('已复制 ' + vLabel, 'success'),
        fail: () =>
          onToast('选人失败，请手动新建消息并粘贴', 'error'),
      });
    };

    if (window.h5sdk && typeof window.h5sdk.ready === 'function') {
      window.h5sdk.ready(run);
    } else if (window.tt) {
      run();
    }
  }

  async function share(apiBase, shareText, vLabel, onToast) {
    try {
      await navigator.clipboard.writeText(shareText);
    } catch {
      onToast('复制失败，请手动复制', 'error');
      return;
    }

    if (isFeishuEnv()) {
      const ready = await ensureSdk(apiBase);
      if (ready) {
        chooseChat(vLabel, onToast);
        return;
      }
      onToast(
        '已复制 ' +
          vLabel +
          '。后端未配置飞书应用，请粘贴后手动发送，或点右上角 ··· → 发送至会话',
        'success'
      );
      return;
    }

    localStorage.setItem(PENDING_KEY, '1');
    onToast('已复制 ' + vLabel + '，正在飞书内打开…', 'success');
    openInFeishuWebview(true);
  }

  async function maybeAutoShare(apiBase, onToast) {
    const params = new URLSearchParams(location.search);
    if (params.get('feishu_share') !== '1') return;
    if (localStorage.getItem(PENDING_KEY) !== '1') return;
    localStorage.removeItem(PENDING_KEY);

    params.delete('feishu_share');
    const clean =
      location.pathname + (params.toString() ? '?' + params.toString() : '');
    history.replaceState(null, '', clean);

    const ready = await ensureSdk(apiBase);
    if (ready) {
      chooseChat('内容', onToast);
      return;
    }
    onToast('已复制到剪贴板，请粘贴发送或点右上角 ··· → 发送至会话', 'success');
  }

  return { share, maybeAutoShare, isFeishuEnv };
})();
