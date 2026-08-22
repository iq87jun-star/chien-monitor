// PoE1相場モニター Service Worker
// データはビルド時にバンドルされる静的サイトのため、
// ・ページ(HTML)はネットワーク優先 → 常に最新デプロイを取得、オフライン時のみキャッシュ
// ・ハッシュ付きアセット(assets/)はキャッシュ優先(内容不変のため)
// ・その他の同一オリジンGET(アイコン・記事ページ等)は stale-while-revalidate
const CACHE = "poe1-monitor-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(["./"]).catch(() => {})),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // gtag等の外部リソースは触らない

  // ページ遷移: ネットワーク優先(最新データを見せる)、失敗時キャッシュ
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((hit) => hit || caches.match("./")),
        ),
    );
    return;
  }

  // ハッシュ付きビルドアセット: キャッシュ優先
  if (url.pathname.includes("/assets/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return res;
          }),
      ),
    );
    return;
  }

  // その他: stale-while-revalidate
  event.respondWith(
    caches.match(req).then((hit) => {
      const refresh = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || refresh;
    }),
  );
});
