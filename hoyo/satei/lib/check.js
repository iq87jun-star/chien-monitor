// チェック式の査定(グラブル・ウマ娘・第五人格)。HoYo のような成約データの学習モデルはまだ無いので、
// 項目ごとの目安額を足し上げて幅を出す。金額は運用しながら PRICE を直す(実際の成約を見て合わせる)
//
// 合わせて「取引しやすさ」(引き戻し・なりすましの心配が少ないか)を見る。
// 取引しにくいアカウントは金額を出さず、DM で個別に確認する

// 項目: k(キー)・label・unit(1あたりの目安額)・max(入力の上限)・cap(加算の上限)
export const CHECK = {
  granblue: {
    label: "グラブル",
    full: "グランブルーファンタジー",
    base: 5000,
    fields: [
      { k: "rank", label: "ランク", hint: "例: 250", unit: 0, max: 500 },
      { k: "limited", label: "リミテッドキャラの数", hint: "例: 80", unit: 700, max: 300 },
      { k: "eternals", label: "十天衆の最終上限解放(人)", hint: "0〜10", unit: 5000, max: 10 },
      { k: "evokers", label: "賢者の加入(人)", hint: "0〜10", unit: 5000, max: 10 },
      { k: "hihi", label: "未使用のヒヒイロカネ(個)", hint: "例: 3", unit: 4000, max: 50, cap: 60000 },
      { k: "kongo", label: "未使用の金剛晶(個)", hint: "例: 2", unit: 3000, max: 50, cap: 30000 },
      { k: "crystal", label: "宝晶石", hint: "例: 30000", unit: 500 / 3000, max: 10_000_000, cap: 40000 },
    ],
    // ランクが低いと、やり込み前提の値付けにならない
    adjust: (v) => (v.rank && v.rank < 150 ? 0.6 : 1),
  },
  umamusume: {
    label: "ウマ娘",
    full: "ウマ娘 プリティーダービー",
    base: 3000,
    fields: [
      { k: "ssr_lb", label: "SSRサポートカード 完凸の枚数", hint: "例: 15", unit: 3000, max: 300 },
      { k: "ssr", label: "SSRサポートカードの所持枚数", hint: "例: 120", unit: 200, max: 500 },
      { k: "uma", label: "育成ウマ娘の所持数", hint: "例: 70", unit: 400, max: 300 },
      { k: "limited", label: "期間限定ウマ娘の数(水着・新衣装など)", hint: "例: 10", unit: 1000, max: 200 },
      { k: "jewel", label: "ジュエル", hint: "例: 30000", unit: 400 / 1500, max: 10_000_000, cap: 40000 },
    ],
    adjust: () => 1,
  },
  identityv: {
    label: "第五人格",
    full: "Identity V 第五人格",
    base: 3000,
    fields: [
      { k: "ssr", label: "SSR以上の衣装の数(UR含む)", hint: "例: 8", unit: 2500, max: 300 },
      { k: "collab", label: "コラボ衣装の数", hint: "例: 10", unit: 1500, max: 200 },
      { k: "s", label: "S衣装の数", hint: "例: 60", unit: 300, max: 1000 },
      { k: "acc", label: "S以上の携帯品の数", hint: "例: 20", unit: 300, max: 500 },
      { k: "echo", label: "エコー", hint: "例: 5000", unit: 0.15, max: 10_000_000, cap: 30000 },
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
