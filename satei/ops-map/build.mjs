// メルル運営マップ(マインドマップ)を、管理画面のデータから作る。
//   SATEI_ADMIN_TOKEN=合言葉 node satei/ops-map/build.mjs 出力先.html
// 毎朝これで作り直して、Artifact(claude.ai/artifact/A6sLqwCdevzJdUYqS4jc74)に公開し直す
import fs from "node:fs";

const API = "https://satei.iq87jun.workers.dev";
const token = process.env.SATEI_ADMIN_TOKEN;
const out = process.argv[2];
if (!token || !out) throw new Error("SATEI_ADMIN_TOKEN と出力先が必要です");
const get = async (path) => {
  const res = await fetch(API + path, { headers: { authorization: `Bearer ${token}`, "user-agent": "Mozilla/5.0" } });
  const d = await res.json();
  if (!d.ok) throw new Error(`${path}: ${d.error ?? res.status}`);
  return d;
};
const [st, cs, stats, sheets, unread] = await Promise.all([
  get("/api/stock"), get("/api/consign"), get("/api/stats?days=30"), get("/api/sheet"), get("/api/portal-unread").then((d) => d.unread),
]);

const now = new Date(Date.now() + 9 * 3600_000); // 日本時間
const today = now.toISOString().slice(0, 10);
const addDays = (d, n) => new Date(Date.parse(d) + n * 86400_000).toISOString().slice(0, 10);
const md = (d) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "—");
const yen = (v) => (v == null ? "未設定" : `${v.toLocaleString("ja-JP")}円`);
const man = (v) => `${(v / 10000).toLocaleString("ja-JP", { maximumFractionDigits: 1 })}万円`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const GAME = { "genshin-impact": "原神", houkaistarrail: "スタレ", zzz: "ゼンゼロ", wutheringwaves: "鳴潮", granblue: "グラブル", umamusume: "ウマ娘", identityv: "第五人格" };
const dl = (rows) => `<dl>${rows.filter(([, v]) => v != null && v !== "").map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
const next = (t) => `<div class='next'><b>次:</b> ${esc(t)}</div>`;
const c6 = (chars) => chars.filter((c) => c.cons === 6);

// ── 在庫 ──
const live = st.stock.filter((s) => s.status !== "売却済み");
const soldRecent = st.stock.filter((s) => s.status === "売却済み" && s.sold_at && s.sold_at >= addDays(today, -30));
const sheetOf = (s) => (s.memo ?? "").match(/シート ?#(\d+)/)?.[1];
const stockItems = [...live, ...soldRecent].map((s) => {
  const top = c6(s.chars).slice(0, 5).map((c) => c.name).join("・");
  const todo = s.status === "未出品" ? "X・Discordに投稿して「出品中」に" : s.price == null && s.status !== "売却済み" ? "販売価格を決める" : "";
  const chip = s.status === "売却済み" ? ["ok", "売却済み"] : s.status === "未出品" ? ["warn", "未出品"] : s.status === "商談中" ? ["warn", "商談中"] : ["ok", "出品中"];
  return {
    t: `No.${s.id} ${GAME[s.game] ?? s.game} 完凸${c6(s.chars).length}体`,
    chip,
    body: dl([
      ["★5", `${s.chars.length}体(完凸${c6(s.chars).length}体)`], ["完凸", top],
      ["仕入れ", s.cost != null ? `${yen(s.cost)}${s.bought_at ? `(${md(s.bought_at)})` : ""}` : null],
      ["販売価格", s.status === "売却済み" ? null : `${yen(s.price)}${s.floor ? `(下限${yen(s.floor)})` : ""}`],
      ["売れた金額", s.sold_price != null ? `${yen(s.sold_price)}(${md(s.sold_at)})` : null],
      ["見込み利益", s.cost != null && s.price != null && s.status !== "売却済み" ? `+${(s.price - s.cost).toLocaleString()}円` : null],
      ["取り返し対策シート", sheetOf(s) ? `あり(#${sheetOf(s)})` : null],
      ["在庫一覧", s.pub ? "公開中" : "非公開"],
    ]) + (todo ? next(todo) : ""),
  };
});

// ── 分割払い ──
const splits = st.split.filter((s) => s.status === "支払い中");
const splitItems = splits.map((s) => {
  const paid = s.pays.filter((p) => p.paid_on).reduce((n, p) => n + p.amount, 0);
  const open = s.pays.filter((p) => !p.paid_on);
  const late = open.filter((p) => p.due_on < today);
  const nx = open[0];
  const chip = late.length ? ["ng", `${late.length}回遅れ`] : unread[s.id] ? ["warn", `新着 ${unread[s.id]}`] : nx && nx.due_on <= addDays(today, 3) ? ["warn", `${md(nx.due_on)} 支払日`] : ["ok", "支払い中"];
  const todo = late.length ? `${md(late[0].due_on)}分の入金を確認・連絡` : unread[s.id] ? "お客様ページのメッセージに返信" : !s.portal ? "お客様ページのリンクを作って送る" : "";
  const mediated = /^【仲介】/.test(s.memo ?? "");
  // 予定表(済み・遅れ・次回が分かるように)
  const table = `<table class='sched'>${s.pays.map((p, k) => `<tr class='${p.paid_on ? "paid" : p.due_on < today ? "late" : p === nx ? "nx" : ""}'><td>${k + 1}回目</td><td>${md(p.due_on)}</td><td class='r'>${yen(p.amount)}</td><td class='r'>${p.paid_on ? `済 ${md(p.paid_on)}` : p.due_on < today ? "遅れ" : p === nx ? "次回" : "予定"}</td></tr>`).join("")}</table>`;
  return {
    t: `No.${s.id} ${s.buyer}さん${mediated ? "(仲介)" : ""} ${nx ? `${md(nx.due_on)} ${(nx.amount / 10000).toLocaleString("ja-JP", { maximumFractionDigits: 1 })}万` : "完済"}`, chip, pay: [paid, s.total],
    body: table + dl([["次回", nx ? `${md(nx.due_on)} ${yen(nx.amount)}` : "なし"], ["残り回数", `${open.length}回`], ["最終回", open.length ? md(open[open.length - 1].due_on) : "—"], ["お客様ページ", s.portal ? "作成済み" : "未作成"]]) + (todo ? next(todo) : ""),
  };
});
const splitLeft = splits.reduce((n, s) => n + s.total - s.pays.filter((p) => p.paid_on).reduce((a, p) => a + p.amount, 0), 0);

// ── 代理出品 ──
const byStatus = {};
for (const c of cs.items) byStatus[c.status] = (byStatus[c.status] ?? 0) + 1;
const selling = cs.items.filter((c) => ["出品中", "代理出品OK"].includes(c.status));
const reply = (byStatus["新規"] ?? 0) + (byStatus["検討中"] ?? 0);
const dueConsign = cs.items.filter((c) => c.next_at && c.next_at <= today && !["成約", "見送り", "重複"].includes(c.status));
const noPrice = [...live.filter((s) => s.pub && s.price == null).map((s) => `在庫 No.${s.id}`), ...selling.filter((c) => c.pub && c.pub_price == null).map((c) => `代理出品 No.${c.id}`)];
const byGame = (list) => Object.entries(list.reduce((m, c) => ((m[GAME[c.game] ?? c.game] ??= []).push(`No.${c.id}`), m), {}));
const consignItems = [
  { t: `販売中 ${selling.length}件`, chip: ["ok", `公開中 ${selling.filter((c) => c.pub).length}件`], body: dl(byGame(selling).map(([g, ns]) => [g, ns.join("・")])) },
  { t: `相談 ${cs.items.length}件の内訳`, body: dl(Object.entries(byStatus)) },
  { t: `定型文 ${cs.templates.length}種`, body: `<p>${cs.templates.map((t) => esc(t.title)).join("<br>")}</p>` },
];

// ── 次にやること ──
const todos = [];
const lateSplits = splitItems.filter((i) => i.chip[0] === "ng");
if (lateSplits.length) todos.push({ t: `分割の入金遅れ ${lateSplits.length}件`, chip: ["ng", "急ぎ"], body: `<ul>${lateSplits.map((i) => `<li>${esc(i.t)}</li>`).join("")}</ul>` });
const unreadN = Object.values(unread).reduce((a, b) => a + b, 0);
if (unreadN) todos.push({ t: `お客様ページの新着 ${unreadN}件`, chip: ["warn", "返信"], body: "<p>在庫と分割の管理 → 分割 → 「💬 お客様ページ・チャット」</p>" });
const soon = splits.flatMap((s) => s.pays.filter((p) => !p.paid_on && p.due_on >= today && p.due_on <= addDays(today, 7)).map((p) => `${md(p.due_on)} ${s.buyer}さん ${yen(p.amount)}`));
if (soon.length) todos.push({ t: `今週の入金予定 ${soon.length}件`, chip: ["info", "確認"], body: `<ul>${soon.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` });
const unlisted = live.filter((s) => s.status === "未出品");
if (unlisted.length) todos.push({ t: `未出品の在庫 ${unlisted.length}件`, chip: ["warn", "投稿"], body: `<p>${unlisted.map((s) => `No.${s.id}`).join("・")} を X・Discord に投稿して「出品中」に。取り返し対策シートがあれば投稿文の1行目に入れる。画像はキャラと武器だけ。</p>` });
if (reply) todos.push({ t: `相談への返信 ${reply}件`, chip: [reply >= 10 ? "ng" : "warn", "たまっている"], body: dl([["新規", `${byStatus["新規"] ?? 0}件`], ["検討中", `${byStatus["検討中"] ?? 0}件`], ["連絡日が来た人", `${dueConsign.length}件`]]) });
if (noPrice.length) todos.push({ t: `公開価格が未設定 ${noPrice.length}件`, chip: ["warn", "決める"], body: `<p>在庫一覧で「お問い合わせ」になっているもの。</p><ul>${noPrice.map((x) => `<li>${x}</li>`).join("")}</ul>` });
const noPortal = splits.filter((s) => !s.portal);
if (noPortal.length) todos.push({ t: `お客様ページ未作成 ${noPortal.length}件`, chip: ["info", "分割"], body: `<p>${noPortal.map((s) => `No.${s.id} ${esc(s.buyer)}さん`).join("・")}</p>` });
if (!todos.length) todos.push({ t: "急ぎの対応はありません", chip: ["ok", "OK"], body: "<p>今日は大きな対応はありません。</p>" });

// ── 買取・査定 ──
const sum = (k) => stats.daily.reduce((n, r) => n + (r[k] || 0), 0);
const recentBuys = st.stock.filter((s) => s.bought_at && s.bought_at >= addDays(today, -30));
const buyItems = [
  { t: "査定ツール(30日)", body: dl([["訪問", sum("visitors")], ["査定", sum("estimates")], ["スクショ読み取り", sum("reads")], ["DMボタン", sum("dms")]]) },
  { t: "買取の流れ", body: "<p>査定 → 確認事項・利用規約に同意 → 引き継ぎフォーム → アカウント情報の提示 → ログイン確認 → メール変更・連携解除 → PayPay支払い → 見守り(1・3・7日)</p>" },
  { t: `最近の買取 ${recentBuys.length}件`, body: recentBuys.length ? dl(recentBuys.map((s) => [md(s.bought_at), `${GAME[s.game] ?? ""}(在庫 No.${s.id})${s.cost != null ? ` ${yen(s.cost)}` : ""}`])) : "<p>この30日の買取はありません。</p>" },
];

// ── 集客 ──
const adsItems = [
  { t: "X @Meruru_Genshin", body: "<p>原神・スタレの窓口。在庫・代理出品の紹介ポスト。</p>" },
  { t: "X @meruru_prop", body: "<p>グラブル・ウマ娘・第五人格の窓口。</p>" },
  { t: "Discord(他鯖)", chip: ["warn", "DM誘導NG"], body: "<p>DM・アカウント名・URLを入れずに投稿。画像はキャラと武器だけ。取り返し対策シートがあれば1行目に入れる。</p>" },
  { t: "在庫一覧ページ", body: `<p>game-souba.com/zaiko/ 。在庫 ${live.filter((s) => s.pub).length}件・代理出品 ${selling.filter((c) => c.pub).length}件を掲載。価格はDMで案内。</p>` },
  { t: `購入希望 ${st.wants.length}件`, chip: ["info", "対応中"], body: st.wants.length ? dl(st.wants.map((w) => [w.name, `${w.status}${w.budget ? `・予算${man(w.budget)}` : ""}`])) : "<p>登録はありません。</p>" },
];

// ── 安全対策・サイト(ほとんど変わらないもの) ──
const safeItems = [
  { t: "確認事項と利用規約", body: "<p>買取の前に確認事項を送り、利用規約(第7条は赤字)に「同意します」と返信をもらう。</p>" },
  { t: "取り返し対策シート", chip: ["ok", `${sheets.items.filter((x) => x.submitted_at).length}件記入済み`], body: `<p>引き継ぎ情報フォームで売主が記入。売るときはPDFにして買い手に渡す。リンク作成 ${sheets.items.length}件・記入済み ${sheets.items.filter((x) => x.submitted_at).length}件。</p>` },
  { t: "引き渡し前の6項目", body: "<p>本人確認・支払い・連携解除・メール変更・パスワード変更・レシート。そろうまで「引き渡し完了」にできない。</p>" },
  { t: "見守り 1・3・7日", body: "<p>引き渡し後にログインできるか確認。「今日やること」に出る。</p>" },
  { t: "完済後に引き渡し", body: "<p>分割払いは基本、完済してから引き渡す。</p>" },
  { t: `要注意リスト ${st.caution.length}件`, body: "<p>過去にトラブルがあったXのユーザー名。同じ人が来ると知らせる。</p>" },
];
const siteItems = [
  { t: "必要なサービス", chip: ["ok", "残す"], body: "<ul><li>GitHub(サイトの置き場所)</li><li>Cloudflare(管理画面・データ)</li><li>Anthropic API(スクショ読み取り)</li><li>ドメイン game-souba.com</li><li>Googleアナリティクス・Discord通知</li></ul>" },
  { t: "整理の候補", chip: ["warn", "検討中"], body: "<ul><li>FF14の記事生成(毎日費用)</li><li>別ドメインのサイト7つ</li><li>toreca-notify・calc-api(Stripe)</li><li>拡張機能・アドイン・Androidアプリ</li><li>X API(@Meruru_Genshin用)</li></ul>" },
  { t: "管理画面", body: "<ul><li>査定ツールの管理:代理出品・利用記録・定型文・引き継ぎ</li><li>在庫と分割:在庫・分割・購入希望・フォロー・要注意・仕入れ検索</li></ul>" },
];

const BRANCHES = [
  { id: "todo", name: "次にやること", color: "var(--b-todo)", side: "L", items: todos },
  { id: "stock", name: "在庫", color: "var(--b-stock)", side: "L", items: stockItems },
  { id: "split", name: "分割払い", color: "var(--b-split)", side: "L", items: splitItems },
  { id: "safe", name: "安全対策", color: "var(--b-safe)", side: "L", items: safeItems },
  { id: "consign", name: "代理出品", color: "var(--b-consign)", side: "R", items: consignItems },
  { id: "buy", name: "買取・査定", color: "var(--b-buy)", side: "R", items: buyItems },
  { id: "ads", name: "集客", color: "var(--b-ads)", side: "R", items: adsItems },
  { id: "site", name: "サイトと費用", color: "var(--b-site)", side: "R", items: siteItems },
];
const KPIS = [
  ["在庫", `${live.length}件${unlisted.length ? `(未出品${unlisted.length})` : ""}`],
  ["分割の残り", man(splitLeft)],
  ["代理出品", `販売中 ${selling.length}件`],
  ["要返信", `${reply}件`],
];
const WD = "日月火水木金土";
const todayLabel = `今日 ${now.getUTCMonth() + 1}月${now.getUTCDate()}日(${WD[now.getUTCDay()]})`;
const asof = `${now.getUTCFullYear()}年${now.getUTCMonth() + 1}月${now.getUTCDate()}日 ${String(now.getUTCHours()).padStart(2, "0")}:${String(now.getUTCMinutes()).padStart(2, "0")}`;
const tpl = fs.readFileSync(new URL("./template.html", import.meta.url), "utf8");
// JSON を <script> に埋めるので、</ を崩しておく
const js = (v) => JSON.stringify(v).replace(/</g, "\\u003c");
fs.writeFileSync(out, tpl.replace("__BRANCHES__", js(BRANCHES)).replace("__KPIS__", js(KPIS)).replace("__ASOF__", asof).replace("__TODAY__", todayLabel));
console.log(`${out} を作りました(${asof})`);
