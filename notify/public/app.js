// 登録ページ。管理キーは localStorage に置き、API に Bearer で送る。
// 相場は拡張と同じ公開 JSON をブラウザで直接読み、検索・現在価格の表示に使う。
import { SOURCES, loadPrices, searchCards, yen } from "./prices.js";

const $ = (id) => document.getElementById(id);
const KEY_STORE = "toreca-notify-key";
const GAME_NOTES = {
  pokeca: "日本語版の欧州相場。カード名に型番(例: 201)やセット名を足すと絞り込めます。",
  yugioh:
    "英語版で最も安い版の欧州相場(日本語版・レアリティ別ではありません)。日本語名で検索できます。",
  onepiece:
    "英語版の米国相場。カード番号(例: OP05-119)か英語名で検索し、版(パラレル等)を選んでください。",
};

let key = null;
let prices = null; // loadPrices() の結果
let me = null; // GET /api/me の結果

function readKey() {
  const m = /[#&]k=([\w-]+)/.exec(location.hash);
  if (m) {
    store(m[1]);
    history.replaceState(null, "", location.pathname);
    return m[1];
  }
  try {
    return localStorage.getItem(KEY_STORE);
  } catch {
    return null;
  }
}
function store(k) {
  try {
    if (k) localStorage.setItem(KEY_STORE, k);
    else localStorage.removeItem(KEY_STORE);
  } catch {
    // 保存できない環境(プライベートブラウズ等)でも、このページを開いている間は使える
  }
}

function status(msg, isError = false) {
  $("status").textContent = msg;
  $("status").className = isError ? "error" : "";
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: {
      "content-type": "application/json",
      ...(key ? { authorization: `Bearer ${key}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error ?? `エラー(${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

const gameName = (cardKey) => SOURCES.find((s) => cardKey.startsWith(`${s.game}:`))?.name ?? "";

function show(view) {
  $("signup").hidden = view !== "signup";
  $("manage").hidden = view !== "manage";
}

async function refresh() {
  try {
    me = await api("GET", "/api/me");
  } catch (err) {
    if (err.status === 401) {
      key = null;
      store(null);
      show("signup");
      status("登録が見つかりませんでした。もう一度登録してください", true);
      return;
    }
    throw err;
  }
  show("manage");
  if (!me.active) {
    status("Discord のウェブフックが削除されたため通知を止めています。登録し直してください", true);
  }
  renderWatches();
  renderPlan();
  renderResults();
}

// 有料プランの案内・お支払い管理(Stripe が設定されている時だけ)
function renderPlan() {
  const box = $("plan");
  box.replaceChildren();
  box.hidden = !me.billing?.available;
  if (box.hidden) return;
  const go = (path) => async () => {
    try {
      location.href = (await api("POST", path)).url;
    } catch (err) {
      status(err.message, true);
    }
  };
  if (me.plan === "pro") {
    box.append(
      el("p", {}, `有料プランをご利用中です(${me.limit}枚まで)。`),
      el(
        "button",
        { type: "button", class: "secondary", onclick: go("/api/portal") },
        "お支払い方法の変更・解約",
      ),
    );
    return;
  }
  const over = me.watches.length > me.limit;
  box.append(
    el(
      "p",
      {},
      `有料プラン(${me.billing.priceLabel})にすると、${me.billing.proLimit}枚まで登録できます。`,
    ),
    over ? el("p", { class: "hint" }, `いまは先に登録した${me.limit}枚だけ通知しています。`) : null,
    el("button", { type: "button", onclick: go("/api/checkout") }, "有料プランにする"),
  );
}

function renderWatches() {
  const list = $("watches");
  list.replaceChildren();
  $("count").textContent = `${me.watches.length} / ${me.limit}枚`;
  $("empty").hidden = me.watches.length > 0;
  for (const w of me.watches) {
    const card = prices?.cards.get(w.cardKey);
    const hit = card && card.jpy <= w.targetJpy;
    list.append(
      el(
        "li",
        {},
        el(
          "span",
          { class: "name" },
          w.label,
          el("span", { class: "sub" }, `${gameName(w.cardKey)}${card ? `・${card.sub}` : ""}`),
        ),
        el(
          "span",
          { class: `price${hit ? " hit" : ""}` },
          card ? `現在 ${yen(card.jpy)}` : prices ? "相場なし" : "…",
        ),
        el("span", {}, `目標 ${yen(w.targetJpy)} 以下`),
        w.notifiedAt && !w.armed ? el("span", { class: "hint" }, "通知済み") : null,
        el(
          "button",
          {
            type: "button",
            class: "small secondary",
            "aria-label": `${w.label} を削除`,
            onclick: async () => {
              try {
                await api("DELETE", `/api/watches/${w.id}`);
                await refresh();
                status(`「${w.label}」を削除しました`);
              } catch (err) {
                status(err.message, true);
              }
            },
          },
          "削除",
        ),
      ),
    );
  }
}

function renderResults() {
  const list = $("results");
  list.replaceChildren();
  const game = document.querySelector("input[name=game]:checked").value;
  $("game-note").textContent = GAME_NOTES[game];
  if (!prices) return;
  const q = $("query").value;
  const found = searchCards(prices.cards, q, { game, limit: 20 });
  if (q.trim() && found.length === 0) {
    list.append(el("li", { class: "hint" }, "見つかりませんでした"));
    return;
  }
  for (const card of found) {
    const input = el("input", {
      type: "number",
      min: "1",
      step: "1",
      required: "",
      value: String(Math.max(1, Math.floor((card.jpy * 0.9) / 10) * 10)),
      "aria-label": `${card.label} の目標額(円)`,
    });
    const form = el(
      "form",
      {
        onsubmit: async (e) => {
          e.preventDefault();
          try {
            await api("POST", "/api/watches", {
              cardKey: card.key,
              label: card.label,
              targetJpy: Number(input.value),
            });
            await refresh();
            status(
              `「${card.label}」を ${yen(Number(input.value))} 以下で通知するよう登録しました`,
            );
          } catch (err) {
            status(err.message, true);
          }
        },
      },
      "目標",
      input,
      "円以下で",
      el("button", { type: "submit" }, "通知"),
    );
    list.append(
      el(
        "li",
        {},
        el("span", { class: "name" }, card.label, el("span", { class: "sub" }, card.sub)),
        el("span", { class: "price" }, yen(card.jpy)),
        form,
      ),
    );
  }
}

$("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = e.submitter ?? e.target.querySelector("button");
  button.disabled = true;
  try {
    const { key: k } = await api("POST", "/api/subscribe", { webhookUrl: $("webhook").value });
    key = k;
    store(k);
    await refresh();
    status("登録しました。Discord に設定用のリンクを送りました");
  } catch (err) {
    status(err.message, true);
  } finally {
    button.disabled = false;
  }
});

$("query").addEventListener("input", renderResults);
for (const r of document.querySelectorAll("input[name=game]")) {
  r.addEventListener("change", renderResults);
}

$("test").addEventListener("click", async () => {
  try {
    await api("POST", "/api/test");
    status("テスト通知を送りました。Discord を確認してください");
  } catch (err) {
    status(err.message, true);
  }
});

$("forget").addEventListener("click", () => {
  key = null;
  store(null);
  show("signup");
  status("");
});

$("delete").addEventListener("click", async () => {
  const paid = me?.plan === "pro" ? "有料プランも解約されます。" : "";
  if (!confirm(`登録したカードと通知先をすべて削除します。${paid}よろしいですか?`)) return;
  try {
    await api("DELETE", "/api/me");
    key = null;
    store(null);
    show("signup");
    status("登録を削除しました");
  } catch (err) {
    status(err.message, true);
  }
});

// Stripe の決済画面から戻ってきた時
if (new URLSearchParams(location.search).has("paid")) {
  history.replaceState(null, "", location.pathname + location.hash);
  status("お申し込みありがとうございます。反映まで少し時間がかかることがあります");
  // Stripe からの通知(Webhook)が届くのを待って、もう一度読み込む
  setTimeout(() => key && refresh().catch(() => {}), 4000);
}

key = readKey();
renderResults();
loadPrices()
  .then((p) => {
    prices = p;
    if (me) renderWatches();
    renderResults();
  })
  .catch(() => status("相場データを読み込めませんでした", true));
if (key) refresh().catch((err) => status(err.message, true));
else show("signup");
