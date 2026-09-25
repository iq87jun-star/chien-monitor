// 物件詳細ページに「単価・月額・初期費用・利回り」のバッジを表示する content script。
// parser.js(globalThis.RealtyParser)と offers.js(globalThis.RealtyOffers)の後に読み込まれる。
// サイトごとのHTML構造に依存しないよう、「賃料」「価格」「専有面積」等の見出し(th・dt・
// 見出しっぽい要素)を探し、その隣の本文を読む。一覧ページ(価格・賃料欄が多数ある)では表示しない。
(() => {
  const R = globalThis.RealtyParser;
  const HOST_ID = "realty-price-checker";
  // 項目名 → 見出しの正規表現。area は上にあるものを優先する(専有面積 > 建物面積 > …)
  const FIELDS = [
    ["rent", /^(賃料|家賃|月額賃料|賃料・初期費用)$/],
    ["fee", /^(管理費・共益費等?|共益費・管理費|管理費等|共益費|管理費)$/],
    ["depositKey", /^(敷金\/礼金|敷\/礼|敷金・礼金)$/],
    ["deposit", /^(敷金|敷金\/保証金|保証金)$/],
    ["keyMoney", /^(礼金|礼金\/償却)$/],
    ["price", /^(価格|販売価格|物件価格)$/],
    ["repair", /^修繕積立金$/],
    ["feeRepair", /^(管理費\/修繕積立|管理費\/修繕積立金|管理費・修繕積立金)$/],
    ["yield", /^(表面利回り|利回り|満室時利回り|想定利回り)$/],
    ["income", /^(満室時年収|想定年間収入|年間想定収入|満室想定年収)$/],
    ["area", /^(専有面積|建物面積|面積|延床面積|使用部分面積)$/],
  ];
  const LABEL_SELECTOR =
    "th, dt, [class*='title'], [class*='label'], [class*='head'], [class*='name'], [class*='term']";
  // 用語解説(「単位は「万円」…」等)を拾わないよう、長い本文は項目の値とみなさない
  const MAX_VALUE = 80;
  // 一覧ページの検索条件の欄(「3万円以下」「下限なし 20m2 25m2 …」)を物件の値とみなさない
  const FILTER_WORDS = /下限なし|上限なし|以下|以上/;
  // 価格・賃料欄の値がこれより多く異なるページは一覧ページとみなす
  const MAX_PRICE_VALUES = 3;

  let lastKey = "";
  let dismissedUrl = "";

  // 見出しの空白・記号・括弧書き(「管理費（月額）」の「（月額）」)と、
  // SUUMO の「ヒント」(用語解説ボタン)を除いて比べる
  const labelOf = (el) =>
    (el.textContent ?? "")
      .normalize("NFKC")
      .replace(/ヒント$/, "")
      .replace(/\([^)]*\)/g, "")
      .replace(/[\s■□◆◇●○★☆【】\[\]<>:：]/g, "")
      .replace(/ヒント$/, "")
      .trim();

  function contentOf(el) {
    if (el.tagName === "TH") {
      const td = el.nextElementSibling?.tagName === "TD" ? el.nextElementSibling : null;
      if (td) return td.innerText;
    }
    let next = el.nextElementSibling;
    while (next && !next.innerText?.trim()) next = next.nextElementSibling;
    return next?.innerText ?? "";
  }

  // { 項目名: [値, …] } を集める(同じ項目の値は出現順)
  function collect() {
    const found = {};
    for (const el of document.querySelectorAll(LABEL_SELECTOR)) {
      if (el.closest(`#${HOST_ID}`)) continue;
      const label = labelOf(el);
      if (!label || label.length > 14) continue;
      const hit = FIELDS.find(([, re]) => re.test(label));
      if (!hit) continue;
      const value = contentOf(el).replace(/\s+/g, " ").trim();
      if (!value || value.length > MAX_VALUE || FILTER_WORDS.test(value)) continue;
      (found[hit[0]] ??= []).includes(value) || found[hit[0]].push(value);
    }
    return found;
  }

  // 見出しのない欄。サイトごとに、見出しが無い時だけ使う要素
  const UNLABELED = {
    // CHINTAI: 賃料が見出しのない td の中の <span class="rent"> にある
    "www.chintai.net": { rent: "span.rent" },
  };
  function collectUnlabeled(found) {
    const sel = UNLABELED[location.hostname] ?? {};
    for (const [key, selector] of Object.entries(sel)) {
      if (found[key]) continue;
      const values = [...document.querySelectorAll(selector)]
        .filter((e) => !e.closest(`#${HOST_ID}`))
        .map((e) => e.innerText.replace(/\s+/g, " ").trim())
        .filter((v) => v && v.length <= MAX_VALUE);
      if (values.length) found[key] = [...new Set(values)];
    }
    return found;
  }

  const man = (yen) => {
    const v = yen / 10000;
    return `${v >= 100 ? Math.round(v).toLocaleString("ja-JP") : Math.round(v * 10) / 10}万円`;
  };
  const yenText = (yen) => (yen >= 100000 ? man(yen) : `${yen.toLocaleString("ja-JP")}円`);
  const pct = (v) => `${Math.round(v * 10000) / 100}%`;

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    for (const c of children) node.append(c);
    return node;
  }
  const row = (label, value, note) =>
    el(
      "div",
      { class: "row" },
      el("div", { class: "label" }, label),
      el("div", { class: "value" }, value),
      note ? el("div", { class: "note" }, note) : "",
    );

  function removeBadge() {
    document.getElementById(HOST_ID)?.remove();
  }

  // 引越し・保険・住宅ローン等の紹介(offers.js に設定がある時だけ・広告であることを明示する)
  function offersNode(kind) {
    const offers = (globalThis.RealtyOffers ?? []).filter((o) => !o.kind || o.kind === kind);
    if (offers.length === 0) return "";
    return el(
      "div",
      { class: "offers" },
      el("div", { class: "pr" }, "PR"),
      ...offers
        .slice(0, 2)
        .map((o) =>
          el("a", { href: o.url, target: "_blank", rel: "noopener sponsored" }, `${o.name} →`),
        ),
    );
  }

  function rowsFor(r) {
    const rows = [];
    const unit =
      r.perM2 != null
        ? `1㎡あたり ${yenText(r.perM2)}・1坪あたり ${yenText(r.perTsubo)}`
        : "面積の記載が読めないため単価は計算できません";
    if (r.kind === "rent") {
      rows.push(
        row(
          "実質の月額(賃料+管理費・共益費)",
          yenText(r.monthly),
          r.fee ? `賃料 ${yenText(r.rent)}＋管理費等 ${yenText(r.fee)}` : "",
        ),
      );
      rows.push(row("広さあたりの月額", unit, r.area ? `専有面積 ${r.area}㎡で計算` : ""));
      if (r.initialCost != null) {
        rows.push(
          row(
            "初期費用の目安(最低限)",
            `約${man(r.initialCost)}`,
            `敷金 ${yenText(r.deposit)}・礼金 ${yenText(r.keyMoney)}・仲介手数料・前家賃1ヶ月。保証会社・火災保険・鍵交換等は別途`,
          ),
        );
      }
    } else {
      rows.push(
        row("価格の単価", unit, r.area ? `面積 ${Math.round(r.area * 100) / 100}㎡で計算` : ""),
      );
      const running = (r.fee ?? 0) + (r.repair ?? 0);
      rows.push(
        row(
          "月々の支払いの目安",
          `約${man(r.monthlyTotal)}`,
          running
            ? `ローン返済 ${man(r.loanPayment)}＋管理費・修繕積立金 ${yenText(running)}`
            : `ローン返済のみ(管理費等の記載なし)`,
        ),
      );
      if (r.grossYield != null) {
        rows.push(
          row(
            "利回り",
            `表面 ${pct(r.grossYield)}${r.netYield != null ? `・簡易実質 ${pct(r.netYield)}` : ""}`,
            [
              r.annualIncome != null ? `年間収入 ${man(r.annualIncome)}` : null,
              r.netYield != null
                ? "簡易実質は管理費・修繕積立金だけを差し引き(税・空室等は含まず)"
                : null,
            ]
              .filter(Boolean)
              .join("・"),
          ),
        );
      }
    }
    return rows;
  }

  function render(r) {
    removeBadge();
    const host = el("div", { id: HOST_ID });
    const root = host.attachShadow({ mode: "open" });
    const style = el("style");
    style.textContent = `
      :host { all: initial; }
      .card { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; width: 300px;
        max-height: 70vh; overflow: auto; box-sizing: border-box;
        background: #fff; color: #1f2937; border: 1px solid #d1d5db; border-radius: 14px;
        box-shadow: 0 8px 28px rgba(0,0,0,.18); padding: 12px 14px;
        font: 13px/1.6 'Hiragino Sans','Noto Sans JP','Yu Gothic',system-ui,sans-serif; }
      .head { display: flex; justify-content: space-between; align-items: center;
        font-size: 12px; color: #1d4ed8; font-weight: 700; margin-bottom: 4px; }
      button { all: unset; cursor: pointer; color: #6b7280; font-size: 16px; padding: 0 4px; }
      .row { border-top: 1px solid #e5e7eb; padding: 6px 0; }
      .label { font-size: 11px; color: #6b7280; }
      .value { font-size: 15px; font-weight: 700; color: #111827; }
      .note { font-size: 11px; color: #6b7280; }
      .foot { border-top: 1px solid #e5e7eb; padding-top: 6px; font-size: 10.5px; color: #9ca3af; }
      .offers { border-top: 1px solid #e5e7eb; padding: 6px 0; }
      .pr { font-size: 10.5px; color: #9ca3af; }
      a { display: block; color: #1d4ed8; font-size: 12px; }
    `;
    const close = el("button", { title: "閉じる", "aria-label": "閉じる" }, "×");
    close.addEventListener("click", () => {
      dismissedUrl = location.href;
      removeBadge();
    });
    const card = el(
      "div",
      { class: "card", role: "complementary", "aria-label": "物件の単価・月額チェック" },
      el(
        "div",
        { class: "head" },
        r.kind === "rent" ? "🏠 家賃チェック" : "🏠 価格チェック",
        close,
      ),
      ...rowsFor(r),
      offersNode(r.kind),
      el(
        "div",
        { class: "foot" },
        `概算です${r.assumptions.length ? `(${r.assumptions.join("・")})` : ""}。実際の条件は不動産会社に確認してください`,
      ),
    );
    root.append(style, card);
    document.documentElement.append(host);
  }

  async function check() {
    const found = collectUnlabeled(collect());
    const key = `${location.href}\n${JSON.stringify(found)}`;
    if (key === lastKey) return;
    lastKey = key;

    const {
      enabled = true,
      loanRate = 1.0,
      loanYears = 35,
    } = await chrome.storage.sync.get(["enabled", "loanRate", "loanYears"]);
    if (!enabled || dismissedUrl === location.href) return removeBadge();
    const priceValues = (found.rent ?? found.price ?? []).length;
    if (priceValues === 0 || priceValues > MAX_PRICE_VALUES) return removeBadge();

    // 同じ項目が複数あれば最初のもの(ページ上部の要約)を使う
    const fields = Object.fromEntries(Object.entries(found).map(([k, v]) => [k, v[0]]));
    const result = R.analyze(fields, {
      loanRate: Number(loanRate) / 100,
      loanYears: Number(loanYears),
    });
    if (result) render(result);
    else removeBadge();
  }

  // DOM の変化が落ち着いて 0.5 秒後に判定する。ずっと変化し続けるページでも
  // 最初の変化から 1.5 秒以内には判定する
  let timer = 0;
  let firstChange = 0;
  const schedule = () => {
    const now = Date.now();
    if (!timer) firstChange = now;
    clearTimeout(timer);
    const wait = Math.max(0, Math.min(500, firstChange + 1500 - now));
    timer = setTimeout(() => {
      timer = 0;
      check().catch((e) => console.warn("realty-price-checker:", e));
    }, wait);
  };
  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  chrome.storage.onChanged.addListener(() => {
    lastKey = "";
    schedule();
  });
  schedule();
})();
