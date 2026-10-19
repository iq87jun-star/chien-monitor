// チェック式の査定(グラブル・ウマ娘・第五人格)。HoYo のような成約データの学習モデルはまだ無いので、
// 項目ごとの目安額を足し上げて幅を出す。金額は運用しながら PRICE を直す(実際の成約を見て合わせる)
//
// 合わせて「取引しやすさ」(引き戻し・なりすましの心配が少ないか)を見る。
// 取引しにくいアカウントは金額を出さず、DM で個別に確認する

// 項目: k(キー)・label・read(スクショで AI が読む時の説明)・unit(1あたりの目安額)・max(入力の上限)・cap(加算の上限)
export const CHECK = {
  granblue: {
    label: "グラブル",
    full: "グランブルーファンタジー",
    shots: "おすすめ: マイページ(ランク・宝晶石)、アイテムの素材画面(ヒヒイロカネ・金剛晶)、キャラ一覧(リミテッド・十天衆・賢者)。",
    base: 5000,
    fields: [
      { k: "rank", label: "ランク", read: "マイページなどに表示される Rank の数字", hint: "例: 250", unit: 0, max: 500 },
      { k: "limited", label: "リミテッドキャラの数", read: "リミテッドキャラの数。合計が表示されていればその数、無ければ「リミテッド」表記のあるキャラを数える", hint: "例: 80", unit: 700, max: 300 },
      { k: "eternals", label: "十天衆の最終上限解放(人)", read: "十天衆のうち最終上限解放済みの人数(0〜10)", hint: "0〜10", unit: 5000, max: 10 },
      { k: "evokers", label: "賢者の加入(人)", read: "加入している賢者の人数(0〜10)", hint: "0〜10", unit: 5000, max: 10 },
      { k: "hihi", label: "未使用のヒヒイロカネ(個)", read: "所持しているヒヒイロカネの個数", hint: "例: 3", unit: 4000, max: 50, cap: 60000 },
      { k: "kongo", label: "未使用の金剛晶(個)", read: "所持している金剛晶の個数", hint: "例: 2", unit: 3000, max: 50, cap: 30000 },
      { k: "crystal", label: "宝晶石", read: "宝晶石の所持数", hint: "例: 30000", unit: 500 / 3000, max: 10_000_000, cap: 40000 },
    ],
    // ランクが低いと、やり込み前提の値付けにならない
    adjust: (v) => (v.rank && v.rank < 150 ? 0.6 : 1),
  },
  umamusume: {
    label: "ウマ娘",
    full: "ウマ娘 プリティーダービー",
    shots: "おすすめ: サポートカード一覧(SSRで絞り込み)、ウマ娘一覧、ジュエルが見える画面。",
    base: 3000,
    fields: [
      { k: "ssr_lb", label: "SSRサポートカード 完凸の枚数", read: "SSRサポートカードのうち完凸(上限解放4回。ダイヤが4つとも埋まっている)の枚数", hint: "例: 15", unit: 3000, max: 300 },
      { k: "ssr", label: "SSRサポートカードの所持枚数", read: "SSRサポートカードの所持枚数", hint: "例: 120", unit: 200, max: 500 },
      { k: "uma", label: "育成ウマ娘の所持数", read: "育成ウマ娘の所持数", hint: "例: 70", unit: 400, max: 300 },
      { k: "limited", label: "期間限定ウマ娘の数(水着・新衣装など)", read: "期間限定ウマ娘(水着・新衣装など)の数", hint: "例: 10", unit: 1000, max: 200 },
      { k: "jewel", label: "ジュエル", read: "ジュエルの所持数", hint: "例: 30000", unit: 400 / 1500, max: 10_000_000, cap: 40000 },
    ],
    adjust: () => 1,
  },
  identityv: {
    label: "第五人格",
    full: "Identity V 第五人格",
    shots: "おすすめ: 衣装の一覧(品質で絞り込み)、携帯品の一覧、エコーが見える画面。",
    base: 3000,
    fields: [
      { k: "ssr", label: "SSR以上の衣装の数(UR含む)", read: "SSR以上(URを含む)の衣装の数", hint: "例: 8", unit: 2500, max: 300 },
      { k: "collab", label: "コラボ衣装の数", read: "コラボ衣装の数", hint: "例: 10", unit: 1500, max: 200 },
      { k: "s", label: "S衣装の数", read: "S衣装の数", hint: "例: 60", unit: 300, max: 1000 },
      { k: "acc", label: "S以上の携帯品の数", read: "S以上の携帯品の数", hint: "例: 20", unit: 300, max: 500 },
      { k: "echo", label: "エコー", read: "エコーの所持数", hint: "例: 5000", unit: 0.15, max: 10_000_000, cap: 30000 },
    ],
    adjust: () => 1,
  },
};

// 取引しやすさの質問(両方のゲームで共通)。答えごとの点数: 2 = 安心 / 1 = 確認が要る / 0 = そのままでは扱えない
export const SAFETY_Q = [
  {
    k: "login",
    short: "引き継ぎ",
    label: "引き継ぎ(ログイン)の方法",
    options: [
      ["id", "ゲーム会社のID(メールとパスワード)", 2],
      ["code", "引き継ぎコード(IDとパスワード)", 2],
      ["sns", "Apple・Google・X などの連携だけ", 0],
      ["unknown", "分からない", 1],
    ],
  },
  {
    k: "mail",
    short: "メール変更",
    label: "登録メールを買い手のものに変えられますか",
    options: [
      ["yes", "はい", 2],
      ["unknown", "分からない", 1],
      ["no", "いいえ", 0],
    ],
  },
  {
    k: "origin",
    short: "入手",
    label: "どんなアカウントですか",
    options: [
      ["self", "自分で作って遊んできた", 2],
      ["bought", "人から買った・譲ってもらった", 0],
    ],
  },
  {
    k: "receipt",
    short: "初回課金レシート",
    label: "初回課金のレシート(メール)は残っていますか",
    options: [
      ["yes", "残っている", 2],
      ["free", "課金していない", 2],
      ["no", "残っていない", 1],
    ],
  },
];

const num = (v, max) => {
  const n = Number(String(v ?? "").normalize("NFKC").replace(/[,\s]/g, ""));
  return Number.isFinite(n) && n > 0 ? Math.min(Math.floor(n), max) : 0;
};

// 取引しやすさ。level: ok(安心)/ check(確認が要る)/ ng(そのままでは扱えない)と、理由
export function safetyOf(answers) {
  const notes = [];
  let ng = false;
  let check = false;
  for (const q of SAFETY_Q) {
    const opt = q.options.find(([v]) => v === answers?.[q.k]);
    if (!opt) { check = true; continue; }
    if (opt[2] === 0) ng = true;
    if (opt[2] === 1) check = true;
  }
  if (answers?.login === "sns") notes.push("連携だけのアカウントは、そのSNSアカウントごと渡すことになり、前の持ち主に取り戻されやすいです");
  if (answers?.mail === "no") notes.push("登録メールを変えられないと、前の持ち主に取り戻されるおそれがあります");
  if (answers?.origin === "bought") notes.push("買ったアカウントは、最初の持ち主に取り戻されるおそれがあり、扱えないことがあります");
  if (answers?.receipt === "no") notes.push("初回課金のレシートが無いと、引き戻しの申し立てを防ぐ材料が減ります");
  return { level: ng ? "ng" : check ? "check" : "ok", notes };
}

// 金額の目安(千円単位)。安全面が ng なら金額は出さない
export function checkEstimate(game, values, answers) {
  const g = CHECK[game];
  if (!g) throw new Error(`unknown game: ${game}`);
  const v = Object.fromEntries(g.fields.map((f) => [f.k, num(values?.[f.k], f.max)]));
  const sum = g.fields.reduce((n, f) => n + Math.min(v[f.k] * f.unit, f.cap ?? Infinity), g.base);
  const mid = sum * g.adjust(v);
  const safety = safetyOf(answers);
  const k = (x) => Math.max(1000, Math.round(x / 1000) * 1000);
  return { values: v, safety, low: safety.level === "ng" ? null : k(mid * 0.7), high: safety.level === "ng" ? null : k(mid * 1.1) };
}

// 管理画面のメモに残す文(答えた内容)
export function checkDetail(game, r, answers) {
  const g = CHECK[game];
  const vals = g.fields.filter((f) => r.values[f.k]).map((f) => `${f.label} ${r.values[f.k].toLocaleString()}`);
  const ans = SAFETY_Q.map((q) => `${q.short}: ${q.options.find(([v]) => v === answers?.[q.k])?.[1] ?? "未回答"}`);
  const level = { ok: "◎ 安心", check: "○ 確認が要る", ng: "× そのままでは扱えない" }[r.safety.level];
  return `[チェック査定] ${vals.join(" / ") || "入力なし"}\n[取引しやすさ] ${level} … ${ans.join(" / ")}`;
}

// スクショの読み取り(Worker の /api/read)。読めない項目は -1 で返してもらう
export function checkSchema(game) {
  const keys = CHECK[game].fields.map((f) => f.k);
  return {
    type: "object",
    additionalProperties: false,
    required: [...keys, "id_visible"],
    properties: { ...Object.fromEntries(keys.map((k) => [k, { type: "integer" }])), id_visible: { type: "boolean" } },
  };
}
export function checkPrompt(game) {
  const g = CHECK[game];
  return `${g.full}のアカウントのスクリーンショットです。次の項目の数を読み取ってください。

${g.fields.map((f) => `- ${f.k}: ${f.read}`).join("\n")}
- id_visible: プレイヤーID・ユーザーID・プレイヤー名などアカウントを特定できる情報が写っていれば true。

画面に写っていない・読み取れない項目は -1 にしてください。推測で数を作らないでください。
同じ項目が複数の画像に出ていたら、大きい方(新しい方)を使ってください。`;
}
// 読み取り結果を入力欄の値にする(-1 や範囲外は「読めなかった」= null)
export function checkValues(game, out) {
  return Object.fromEntries(CHECK[game].fields.map((f) => [f.k, Number.isInteger(out?.[f.k]) && out[f.k] >= 0 ? Math.min(out[f.k], f.max) : null]));
}
