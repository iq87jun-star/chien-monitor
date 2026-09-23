// 商品ページに海外相場バッジを表示する content script。
// matcher.js(globalThis.PokecaMatcher)の後に読み込まれる。
// メルカリ等のSPAはページ遷移でリロードしないため、URLとタイトルの変化を監視して再判定する。
(() => {
  const M = globalThis.PokecaMatcher;
  const SITE_URL = "https://pokeca-kaigai.com/";
  const HOST_ID = "pokeca-kaigai-checker";
  const MAX_CANDIDATES = 3;

  let index = null;
  let lastKey = "";
  let dismissedUrl = "";

  const yen = (n) => (n == null ? "-" : `¥${n.toLocaleString("ja-JP")}`);
  const eur = (n) => (n == null ? "-" : `€${n.toFixed(2)}`);

  // 商品名を取る: h1 が最も確実(メルカリ・ヤフオク・駿河屋・ラクマ共通)。無ければ <title>
  function productTitle() {
    const h1 = document.querySelector("h1");
    const text = h1?.textContent?.trim();
    return text && text.length >= 3 ? text : document.title;
  }

  function removeBadge() {
    document.getElementById(HOST_ID)?.remove();
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    for (const c of children) node.append(c);
    return node;
  }

  function changeNode(card) {
    const pct = M.change7d(card);
    if (pct == null) return "";
    const cls = pct > 0 ? "up" : pct < 0 ? "down" : "";
    return el("span", { class: `chg ${cls}` }, `7日平均比 ${pct > 0 ? "+" : ""}${pct}%`);
  }

  function hitNode(hit) {
    const top = hit.cards[0];
    const box = el("div", { class: "hit" });
    box.append(el("div", { class: "name" }, hit.name));
    if (hit.exact) {
      box.append(
        el("div", { class: "meta" }, `${top.setName} ${top.localId}`),
        el(
          "div",
          { class: "price" },
          el("b", {}, `約${yen(M.toJpy(index, top.eur))}`),
          el("span", { class: "sub" }, ` (${eur(top.eur)})`),
          " ",
          changeNode(top),
        ),
      );
    } else {
      // 同名カードが複数ある場合は価格幅と上位候補を出す(型番を書かない出品が多いため)
      const prices = hit.cards.map((c) => c.eur);
      const lo = M.toJpy(index, Math.min(...prices));
      const hi = M.toJpy(index, Math.max(...prices));
      box.append(
        el("div", { class: "price" }, el("b", {}, `約${yen(lo)}〜${yen(hi)}`)),
        el("div", { class: "meta" }, `同名カード${hit.cards.length}種(型番で絞り込めます)`),
      );
      const list = el("ul");
      for (const c of hit.cards.slice(0, MAX_CANDIDATES)) {
        list.append(el("li", {}, `${c.setName} ${c.localId}: 約${yen(M.toJpy(index, c.eur))}`));
      }
      box.append(list);
    }
    return box;
  }

  function render(hits) {
    removeBadge();
    const host = el("div", { id: HOST_ID });
    const root = host.attachShadow({ mode: "open" });
    const style = el("style");
    style.textContent = `
      :host { all: initial; }
      .card { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; width: 300px;
        max-height: 70vh; overflow: auto; box-sizing: border-box;
        background: #0B0E17; color: #E8E6E0; border: 1px solid #2A3350; border-radius: 14px;
        box-shadow: 0 8px 28px rgba(0,0,0,.35); padding: 12px 14px;
        font: 13px/1.6 'Hiragino Sans','Noto Sans JP','Yu Gothic',system-ui,sans-serif; }
      .head { display: flex; justify-content: space-between; align-items: center;
        font-size: 12px; color: #EBCB7A; font-weight: 700; margin-bottom: 6px; }
      button { all: unset; cursor: pointer; color: #A9ACB8; font-size: 16px; padding: 0 4px; }
      .hit { border-top: 1px solid #2A3350; padding: 8px 0; }
      .name { font-weight: 700; color: #fff; font-size: 14px; }
      .meta { color: #A9ACB8; font-size: 12px; }
      .price b { font-size: 17px; color: #EBCB7A; }
      .sub { color: #A9ACB8; font-size: 12px; }
      .chg { font-size: 12px; white-space: nowrap; }
      .up { color: #5FD08A; } .down { color: #F07A7A; }
      ul { margin: 4px 0 0; padding-left: 16px; color: #A9ACB8; font-size: 12px; }
      a { color: #EBCB7A; font-size: 12px; }
      .foot { border-top: 1px solid #2A3350; padding-top: 8px; font-size: 11px; color: #6E7284; }
    `;
    const close = el("button", { title: "閉じる", "aria-label": "閉じる" }, "×");
    close.addEventListener("click", () => {
      dismissedUrl = location.href;
      removeBadge();
    });
    const updated = index.fetchedAt ? new Date(index.fetchedAt).toLocaleDateString("ja-JP") : "";
    const link = el(
      "a",
      {
        href: `${SITE_URL}?utm_source=extension&utm_medium=badge`,
        target: "_blank",
        rel: "noopener",
      },
      "高騰・下落ランキングを見る →",
    );
    const card = el(
      "div",
      { class: "card", role: "complementary", "aria-label": "ポケカ海外相場" },
      el("div", { class: "head" }, "🌍 海外相場(Cardmarket・日本語版)", close),
      ...hits.map(hitNode),
      el(
        "div",
        { class: "foot" },
        link,
        el("div", {}, `${updated}更新・欧州の取引平均を円換算した参考値です`),
      ),
    );
    root.append(style, card);
    document.documentElement.append(host);
  }

  async function check() {
    const title = productTitle();
    const key = `${location.href}\n${title}`;
    if (key === lastKey) return;
    lastKey = key;

    const { enabled = true } = await chrome.storage.sync.get("enabled");
    if (!enabled || dismissedUrl === location.href) return removeBadge();

    if (!index) {
      const data = await chrome.runtime.sendMessage({ type: "getData" });
      index = M.buildIndex(data);
      if (!index) return;
    }
    const hits = M.match(index, title);
    if (hits) render(hits);
    else removeBadge();
  }

  let timer = 0;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(() => check().catch((e) => console.warn("pokeca-checker:", e)), 400);
  };
  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.enabled) {
      lastKey = "";
      schedule();
    }
  });
  schedule();
})();
