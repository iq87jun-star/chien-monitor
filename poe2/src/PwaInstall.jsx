import { useEffect, useState } from "react";

// PWAまわりのUI: Service Worker登録・インストール誘導・更新通知
// theme には App.jsx の配色オブジェクト T を渡す
const DISMISS_KEY = "poe2:pwa-install-dismissed";

const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  window.navigator.standalone === true;

const isIos = () =>
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

export default function PwaInstall({ theme: T }) {
  const [installEvent, setInstallEvent] = useState(null);
  const [showIosHint, setShowIosHint] = useState(false);
  const [waitingWorker, setWaitingWorker] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
    let reg;
    const onControllerChange = () => window.location.reload();
    navigator.serviceWorker
      .register("./sw.js")
      .then((r) => {
        reg = r;
        if (r.waiting && navigator.serviceWorker.controller) setWaitingWorker(r.waiting);
        r.addEventListener("updatefound", () => {
          const w = r.installing;
          if (!w) return;
          w.addEventListener("statechange", () => {
            if (w.state === "installed" && navigator.serviceWorker.controller)
              setWaitingWorker(w);
          });
        });
      })
      .catch(() => {});
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    return () =>
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
  }, []);

  useEffect(() => {
    if (isStandalone()) return;
    const onPrompt = (e) => {
      e.preventDefault();
      setInstallEvent(e);
    };
    const onInstalled = () => setInstallEvent(null);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    if (isIos()) setShowIosHint(true);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* private mode等では保存しない */
    }
  };

  const bannerStyle = {
    position: "fixed",
    left: "50%",
    bottom: 16,
    transform: "translateX(-50%)",
    width: "min(480px, calc(100vw - 24px))",
    background: T.surface,
    border: `1px solid ${T.gold}`,
    borderRadius: T.r.md,
    boxShadow: "0 6px 24px rgba(0,0,0,0.6)",
    padding: "12px 14px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    zIndex: 100,
    fontSize: 13,
    color: T.text,
  };

  const btn = {
    background: T.gold,
    color: T.bg,
    border: "none",
    borderRadius: T.r.full,
    padding: "8px 16px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  };

  const closeBtn = {
    background: "none",
    border: "none",
    color: T.textLow,
    fontSize: 18,
    cursor: "pointer",
    padding: "2px 6px",
    lineHeight: 1,
  };

  // 新バージョン通知は誘導バナーより優先して出す
  if (waitingWorker) {
    return (
      <div style={bannerStyle} role="status">
        <span style={{ flex: 1 }}>新しいバージョンがあります</span>
        <button
          style={btn}
          onClick={() => waitingWorker.postMessage({ type: "SKIP_WAITING" })}
        >
          更新する
        </button>
      </div>
    );
  }

  if (dismissed || isStandalone()) return null;

  if (installEvent) {
    return (
      <div style={bannerStyle}>
        <span style={{ flex: 1 }}>
          📱 アプリとしてインストールすると、ホーム画面からすぐ相場を確認できます
        </span>
        <button
          style={btn}
          onClick={async () => {
            installEvent.prompt();
            const { outcome } = await installEvent.userChoice;
            setInstallEvent(null);
            if (outcome === "dismissed") dismiss();
          }}
        >
          追加
        </button>
        <button style={closeBtn} onClick={dismiss} aria-label="閉じる">
          ✕
        </button>
      </div>
    );
  }

  if (showIosHint) {
    return (
      <div style={bannerStyle}>
        <span style={{ flex: 1, lineHeight: 1.6 }}>
          📱 共有ボタン
          <span style={{ color: T.goldLight, margin: "0 2px" }}>(□↑)</span>→
          「ホーム画面に追加」でアプリとして使えます
        </span>
        <button style={closeBtn} onClick={dismiss} aria-label="閉じる">
          ✕
        </button>
      </div>
    );
  }

  return null;
}
