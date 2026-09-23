// 求人詳細ページに「年収目安・時給換算・固定残業代」のバッジを表示する content script。
// parser.js(globalThis.JobParser)と offers.js(globalThis.JobOffers)の後に読み込まれる。
// サイトごとのHTML構造に依存しないよう、「給与」「勤務時間」等の見出し(th・dt・見出しタグ)を探し、
// その隣の本文を読む。一覧ページ(給与欄が多数ある)では表示しない。
// Indeed 等のSPAはページ遷移でリロードしないため、DOMの変化を監視して再判定する。
(() => {
  const P = globalThis.JobParser;
  const HOST_ID = "job-salary-checker";
  const SALARY_LABELS =
    /^(給与|給与・待遇|給与・賞与|給与・報酬|想定年収|年収|賃金|給料|報酬|基本給)$/;
  const WORK_LABELS = /^(勤務時間|就業時間|勤務時間・休日|休日・休暇|休日休暇|休日|年間休日)$/;
  const LABEL_SELECTOR =
    "th, dt, h2, h3, h4, h5, [class*='title'], [class*='label'], [class*='head']";
  // 給与欄がこれより多いページは一覧ページとみなす(詳細ページでも要約と本文で2つあることがある)
  const MAX_SALARY_BLOCKS = 3;
  const MAX_TEXT = 1500;

  let lastKey = "";
  let dismissedUrl = "";

  // 見出しの記号(■【】◆ 等)と空白を除いて比べる
  const labelOf = (el) =>
    (el.textContent ?? "").replace(/[\s■□◆◇●○★☆【】\[\]<>＜＞:：]/g, "").trim();

  // 見出しに対応する本文: th→同じ行のtd、dt→次のdd、それ以外→次の兄弟要素
  function contentOf(el) {
    if (el.tagName === "TH") {
      const td = el.parentElement?.querySelector("td");
      if (td) return td.innerText;
    }
    let next = el.nextElementSibling;
    while (next && !next.innerText?.trim()) next = next.nextElementSibling;
    return next?.innerText ?? "";
  }

  function collect(re) {
    const texts = [];
    for (const el of document.querySelectorAll(LABEL_SELECTOR)) {
      if (el.closest(`#${HOST_ID}`)) continue;
      const label = labelOf(el);
      if (label.length > 10 || !re.test(label)) continue;
      // 見出しも付けて渡す(「想定年収」欄の本文が「400万円～600万円」だけの場合に備える)
      const body = contentOf(el).trim().slice(0, MAX_TEXT);
      const text = body && `${label}：${body}`;
      if (text && !texts.includes(text)) texts.push(text);
    }
    return texts;
  }

  const man = (yen) => {
    const v = yen / 10000;
    return `${v >= 100 ? Math.round(v) : Math.round(v * 10) / 10}万`;
  };
  // 上限なしの幅(「30万円～」)だけ末尾に「〜」を付け、単独の金額(「年収例 550万円」)には付けない
  const range = (r, unit = "円") =>
    r.max ? `${man(r.min)}〜${man(r.max)}${unit}` : `${man(r.min)}${unit}${r.open ? "〜" : ""}`;
  const yenRange = (r, open) =>
    r.max
      ? `${r.min.toLocaleString("ja-JP")}〜${r.max.toLocaleString("ja-JP")}円`
      : `${r.min.toLocaleString("ja-JP")}円${open ? "〜" : ""}`;

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

  // 転職エージェント等の紹介(offers.js に設定がある時だけ・広告であることを明示する)
  function offersNode(r) {
    const offers = (globalThis.JobOffers ?? []).filter(
      (o) => !o.minAnnual || (r.annual?.min ?? r.stated?.min ?? 0) >= o.minAnnual,
    );
    if (offers.length === 0) return "";
    return el(
      "div",
      { class: "offers" },
      el("div", { class: "pr" }, "PR・この条件に近い求人を探す"),
      ...offers
        .slice(0, 2)
        .map((o) =>
          el("a", { href: o.url, target: "_blank", rel: "noopener sponsored" }, `${o.name} →`),
        ),
    );
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
        font-size: 12px; color: #0f766e; font-weight: 700; margin-bottom: 4px; }
      button { all: unset; cursor: pointer; color: #6b7280; font-size: 16px; padding: 0 4px; }
      .row { border-top: 1px solid #e5e7eb; padding: 6px 0; }
      .label { font-size: 11px; color: #6b7280; }
      .value { font-size: 16px; font-weight: 700; color: #111827; }
      .note { font-size: 11px; color: #6b7280; }
      .warn .value { color: #b45309; font-size: 13px; }
      .foot { border-top: 1px solid #e5e7eb; padding-top: 6px; font-size: 10.5px; color: #9ca3af; }
      .offers { border-top: 1px solid #e5e7eb; padding: 6px 0; }
      .pr { font-size: 10.5px; color: #9ca3af; }
      a { display: block; color: #0f766e; font-size: 12px; }
    `;
    const close = el("button", { title: "閉じる", "aria-label": "閉じる" }, "×");
    close.addEventListener("click", () => {
      dismissedUrl = location.href;
      removeBadge();
    });

    const rows = [];
    if (r.annual) {
      const a = r.annual;
      const how =
        a.from === "年俸"
          ? "求人に記載の年俸"
          : a.bonusIncluded
            ? `${a.from}ベースの月額×12＋賞与${r.bonusMonths}ヶ月分で計算`
            : `${a.from}ベースの月額×12で計算(賞与の月数の記載なし・賞与を含まず)`;
      rows.push(row("年収目安", `約${range(r.annual)}`, how));
    }
    if (r.stated) {
      rows.push(
        row(
          r.stated.companyAverage ? "会社の平均年収(記載)" : `求人に記載の年収(${r.stated.kind})`,
          range(r.stated),
          r.stated.companyAverage ? "この求人の年収ではなく会社全体の平均です" : "",
        ),
      );
    }
    if (r.hourlyEquivalent) {
      rows.push(
        row(
          "時給に換算すると",
          `約${yenRange(r.hourlyEquivalent, r.annual?.open)}`,
          r.fixedOvertime
            ? "固定残業代を含む月給÷所定時間で計算(実質はこれより低い)"
            : "残業代を含まない所定時間で計算",
        ),
      );
    }
    if (r.fixedOvertime) {
      const fo = r.fixedOvertime;
      const detail = [fo.hours && `月${fo.hours}時間分`, fo.amount && `${man(fo.amount)}円`]
        .filter(Boolean)
        .join("・");
      const without = r.baseWithoutOvertime
        ? `除いた月給 ${man(r.baseWithoutOvertime.monthly)}円(時給換算 約${r.baseWithoutOvertime.hourly.toLocaleString("ja-JP")}円)`
        : "金額の記載がないため除いた額は計算できません";
      const warn = row("⚠ 固定残業代を含む給与です", detail || "時間・金額の記載なし", without);
      warn.classList.add("warn");
      rows.push(warn);
    }
    const assume = [
      r.hoursPerDay ? `実働${Math.round(r.hoursPerDay * 100) / 100}時間` : null,
      r.holidays ? `年間休日${r.holidays}日` : null,
      ...r.assumptions.map((a) => `${a}と仮定`),
    ].filter(Boolean);

    const card = el(
      "div",
      { class: "card", role: "complementary", "aria-label": "求人の年収チェック" },
      el("div", { class: "head" }, "💴 年収チェック", close),
      ...rows,
      offersNode(r),
      el(
        "div",
        { class: "foot" },
        `概算です(${assume.join("・")})。実際の条件は求人元に確認してください`,
      ),
    );
    root.append(style, card);
    document.documentElement.append(host);
  }

  async function check() {
    const salaryTexts = collect(SALARY_LABELS);
    const key = `${location.href}\n${salaryTexts.join("|")}`;
    if (key === lastKey) return;
    lastKey = key;

    const { enabled = true } = await chrome.storage.sync.get("enabled");
    if (!enabled || dismissedUrl === location.href) return removeBadge();
    if (salaryTexts.length === 0 || salaryTexts.length > MAX_SALARY_BLOCKS) return removeBadge();

    const result = P.analyze(salaryTexts.join("\n"), collect(WORK_LABELS).join("\n"));
    if (result.found) render(result);
    else removeBadge();
  }

  let timer = 0;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(() => check().catch((e) => console.warn("job-salary-checker:", e)), 500);
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
