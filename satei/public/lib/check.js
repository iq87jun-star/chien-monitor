// チェック式の査定(グラブル・ウマ娘・第五人格)。ゲームトレードで売れたアカウント(gametrade-watch の記録)から
// log(売値) をリッジ回帰で学習したモデル(public/check-model.json、satei/scripts/train-check.mjs)で相場を出す。
// 特徴量は項目ごとの log(1+数)。学習では出品の項目欄とタイトルから数を読む(listingValues)
//
// 合わせて「取引しやすさ」(引き戻し・なりすましの心配が少ないか)を見る。
// 取引しにくいアカウントは金額を出さず、DM で個別に確認する

// 項目: k(キー)・label・read(スクショで AI が読む時の説明)・hint・max(入力の上限)
//   options があれば選択式([値, 表示])
export const CHECK = {
  granblue: {
    label: "グラブル",
    full: "グランブルーファンタジー",
    shots: "おすすめ: マイページ(ランク・宝晶石)、キャラ一覧(SSRの数・十天衆・賢者)、アイテムの素材画面(ヒヒイロカネ・金剛晶)。",
    fields: [
      { k: "rank", label: "ランク", read: "マイページなどに表示される Rank の数字", hint: "例: 250", max: 999 },
      { k: "ssr", label: "SSRキャラの数", read: "所持している SSR キャラの数", hint: "例: 400", max: 2000 },
      { k: "crystal", label: "宝晶石", read: "宝晶石の所持数", hint: "例: 30000", max: 10_000_000 },
      { k: "eternals", label: "十天衆の最終上限解放(人)", read: "十天衆のうち最終上限解放済みの人数(0〜10)", hint: "0〜10", max: 10 },
      { k: "evokers", label: "賢者の加入(人)", read: "加入している賢者の人数(0〜10)", hint: "0〜10", max: 10 },
      { k: "hihi", label: "未使用のヒヒイロカネ(個)", read: "所持しているヒヒイロカネの個数", hint: "例: 3", max: 999 },
      { k: "kongo", label: "未使用の金剛晶(個)", read: "所持している金剛晶の個数", hint: "例: 2", max: 999 },
    ],
  },
  umamusume: {
    label: "ウマ娘",
    full: "ウマ娘 プリティーダービー",
    shots: "おすすめ: サポートカード一覧(SSRで絞り込み)、ウマ娘一覧、ジュエルとチームランクが見える画面。",
    fields: [
      { k: "teamss", label: "チームランク", read: "チーム競技場のチームランクが SS 以上なら 1、それ以外は 0", options: [["1", "SS以上"], ["0", "S以下・分からない"]], max: 1 },
      { k: "ssr", label: "SSRサポートカードの所持枚数", read: "SSRサポートカードの所持枚数", hint: "例: 100", max: 999 },
      { k: "ssr_lb", label: "SSRサポートカード 完凸の枚数", read: "SSRサポートカードのうち完凸(上限解放4回。ダイヤが4つとも埋まっている)の枚数", hint: "例: 15", max: 999 },
      { k: "star3", label: "星3ウマ娘の数", read: "星3(才能開花前の初期★3)ウマ娘の数", hint: "例: 60", max: 999 },
      { k: "jewel", label: "ジュエル", read: "ジュエルの所持数", hint: "例: 30000", max: 10_000_000 },
    ],
  },
  identityv: {
    label: "第五人格",
    full: "Identity V 第五人格",
    shots: "おすすめ: 衣装の一覧(品質で絞り込み)、ランク(段位)が見える画面。",
    fields: [
      { k: "survivor", label: "サバイバーの段位", read: "サバイバーの段位。1段〜7段は 1〜7、最高峰7段は 8", options: [["0", "分からない"], ...[1, 2, 3, 4, 5, 6, 7].map((n) => [String(n), `${n}段`]), ["8", "最高峰7段"]], max: 8 },
      { k: "hunter", label: "ハンターの段位", read: "ハンターの段位。1段〜7段は 1〜7、最高峰7段は 8", options: [["0", "分からない"], ...[1, 2, 3, 4, 5, 6, 7].map((n) => [String(n), `${n}段`]), ["8", "最高峰7段"]], max: 8 },
      { k: "ur", label: "UR・LR衣装の数", read: "UR・LR 品質の衣装の数", hint: "例: 2", max: 999 },
      { k: "ssr", label: "SSR衣装の数", read: "SSR 品質の衣装の数", hint: "例: 10", max: 999 },
      { k: "collab", label: "コラボ衣装の数", read: "コラボ衣装の数", hint: "例: 5", max: 999 },
    ],
  },
};
// gametrade-watch の記録のゲーム名(ゲームトレードの URL 名)
export const SOLD_GAME = { granblue: "granblue", umamusume: "umamusume", identityv: "identity-v" };

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
export const cleanValues = (game, values) => Object.fromEntries(CHECK[game].fields.map((f) => [f.k, num(values?.[f.k], f.max)]));

// 特徴量: 切片・項目ごとの log(1+数)・出品だけにある印(初期垢など。査定では 0)。
// 項目の重みは 0 以上に限る(数が多いほど安くなる、という査定にしない)
export const EXTRA = ["starter"];
export const checkFeatureNames = (game) => ["bias", ...CHECK[game].fields.map((f) => `log:${f.k}`), ...EXTRA];
export function checkFeatures(game, values, extra = {}) {
  const v = cleanValues(game, values);
  return [1, ...CHECK[game].fields.map((f) => Math.log1p(v[f.k])), ...EXTRA.map((k) => (extra[k] ? 1 : 0))];
}

// ── 学習用: 出品(ゲームトレードの売れた記録)から項目の数を読む ──
const n = (s) => Number(String(s).replace(/,/g, ""));
// 項目欄(「ランク：201」など)。0・1 は未入力のことが多いので読まない
function info(row, re) {
  for (const i of row.info ?? []) {
    const m = re.exec(i.normalize("NFKC"));
    if (m && n(m[1]) > 1) return n(m[1]);
  }
  return 0;
}
const first = (t, ...res) => {
  for (const re of res) {
    const m = re.exec(t);
    if (m) return n(m[1]);
  }
  return 0;
};
// 「十天」「賢者」のように人数が書かれにくいもの: 書かれた人数(10 まで)。「×10」「最終」「コンプ」などは 10、言及だけなら 5
function people(t, re) {
  const m = re.exec(t);
  if (!m) return 0;
  const rest = t.slice(m.index, m.index + 16);
  if (/最終|輝|コンプ|全|[x×]\s*10/.test(rest)) return 10;
  const k = /(\d{1,2})(?!\d)/.exec(rest.slice(m[0].length));
  return k && n(k[1]) <= 10 ? n(k[1]) : 5;
}
const DAN = (s) => (/最高峰/.test(s) ? 8 : Number(/(\d)段/.exec(s)?.[1] ?? 0));
// アカウントではない出品(特典コード・グッズなど)。学習から除く
export const NOT_ACCOUNT = /特典|シリアル|コード|チケット|パック|グッズ|アクスタ|来場者|Relink|GBVS/i;

export function listingValues(game, row) {
  const t = String(row.name ?? "").normalize("NFKC");
  const extra = { starter: /初期|リセマラ/.test(t) };
  if (game === "granblue") {
    return {
      values: {
        rank: info(row, /ランク:(\d+)/) || first(t, /(?:rank|ランク|ﾗﾝｸ)\s*(\d{2,3})/i),
        ssr: info(row, /SSRキャラクターの数:(\d+)/) || first(t, /SSR(?:キャラ)?(?:計|数)?\s*(\d{2,4})/i),
        crystal: info(row, /宝晶石の数:(\d+)/) || first(t, /(?:宝晶石|石)(?:換算)?\s*(\d+(?:\.\d+)?)\s*万/) * 10000,
        eternals: people(t, /十天(?:衆)?/),
        evokers: people(t, /賢者|十賢|終賢/),
        hihi: first(t, /ヒヒ(?:イロ(?:カネ)?)?\s*[x×]?\s*(\d{1,3})/),
        kongo: first(t, /金剛(?:晶)?\s*[x×]?\s*(\d{1,3})/),
      },
      extra,
    };
  }
  if (game === "umamusume") {
    const lb = first(t, /完凸(?:サポ(?:カ|ート)?)?\s*(\d{1,3})/, /(\d{1,3})\s*(?:枚|体)?\s*完凸/);
    return {
      values: {
        teamss: (row.info ?? []).some((i) => /チームランク:SS/.test(i.normalize("NFKC"))) ? 1 : 0,
        ssr: info(row, /SSRサポートカードの数:(\d+)/) || first(t, /SSR(?:サポ(?:カ|ート)?)?\s*(\d{2,3})/i),
        ssr_lb: lb || (/完凸/.test(t) ? 3 : 0),
        star3: info(row, /星3ウマ娘の数:(\d+)/),
        jewel: info(row, /ジュエルの数:(\d+)/) || first(t, /(?:石|ジュエル)\s*(\d+(?:\.\d+)?)\s*万/) * 10000,
      },
      extra,
    };
  }
  if (game === "identityv") {
    const get = (k) => (row.info ?? []).map((i) => i.normalize("NFKC")).find((i) => i.startsWith(k)) ?? "";
    return {
      values: {
        survivor: DAN(get("サバイバーランク")),
        hunter: DAN(get("ハンターランク")),
        ur: first(t, /(?:UR|LR)\s*(?:衣装)?\s*[x×]?\s*(\d{1,3})/i) || (/UR|LR/i.test(t) ? 1 : 0),
        ssr: first(t, /SSR\s*(?:衣装)?\s*[x×]?\s*(\d{1,3})/i) || (/SSR/i.test(t) ? 1 : 0),
        collab: first(t, /コラボ(?:衣装)?\s*[x×]?\s*(\d{1,3})/) || (/コラボ/.test(t) ? (/コンプ/.test(t) ? 5 : 1) : 0),
      },
      extra,
    };
  }
  throw new Error(`unknown game: ${game}`);
}

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

const yen = (x, round) => Math.max(1000, round(x / 1000) * 1000);
// 金額の目安。model は public/check-model.json の中身。
// 返り値: market = 代理出品の相場(売値の幅)、low/high = 買取額の幅。安全面が ng なら金額は出さない
export function checkEstimate(model, game, values, answers) {
  const g = CHECK[game];
  if (!g) throw new Error(`unknown game: ${game}`);
  const m = model.games[game];
  if (!m || m.features.join() !== checkFeatureNames(game).join()) throw new Error("モデルと項目が合っていません");
  const v = cleanValues(game, values);
  const safety = safetyOf(answers);
  if (safety.level === "ng") return { values: v, safety, low: null, high: null, market: null };
  const mid = Math.exp(m.weights.reduce((s, w, i) => s + w * checkFeatures(game, v)[i], 0));
  // 学習データの上限を超える時は、上限で止めて個別査定にする
  const capped = mid * Math.exp(m.band[1]) > m.cap;
  const lo = Math.min(mid * Math.exp(m.band[0]), m.cap);
  const hi = Math.min(mid * Math.exp(m.band[1]), m.cap);
  return {
    values: v,
    safety,
    capped,
    market: { low: yen(lo, Math.floor), high: yen(hi, Math.ceil) },
    low: yen(lo * model.buyRate, Math.floor),
    high: yen(hi * model.buyRate, Math.ceil),
  };
}

// 管理画面のメモに残す文(答えた内容)
export function checkDetail(game, r, answers) {
  const g = CHECK[game];
  const show = (f) => (f.options ? f.options.find(([o]) => o === String(r.values[f.k]))?.[1] : r.values[f.k].toLocaleString());
  const vals = g.fields.filter((f) => r.values[f.k]).map((f) => `${f.label} ${show(f)}`);
  const ans = SAFETY_Q.map((q) => `${q.short}: ${q.options.find(([v]) => v === answers?.[q.k])?.[1] ?? "未回答"}`);
  const level = { ok: "◎ 安心", check: "○ 確認が要る", ng: "× そのままでは扱えない" }[r.safety.level];
  const price = r.market ? ` / 相場 ${r.market.low.toLocaleString()}〜${r.market.high.toLocaleString()}円` : "";
  return `[チェック査定] ${vals.join(" / ") || "入力なし"}${price}\n[取引しやすさ] ${level} … ${ans.join(" / ")}`;
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
