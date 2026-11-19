// CS2 スキンの模擬売買(お金は動かさない)。1 日 1 回、Skinport の相場(鍵なし)を読み、上昇中でよく売れている品を仮に買い、
// 持っている仮の品を値洗いして決まりに沿って仮に売る。結果を Discord に送る。記録は state/cs2.json、決まりは config.json の cs2。
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { emptyPaper, step, buy, summary, compareText } from "./src/paper.js";
import { joinMarket, sellRef, pickItems } from "./src/cs2.js";

const env = process.env;
const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url), "utf8"));
const cc = cfg.cs2 || {};
const FILE = new URL("./state/cs2.json", import.meta.url);
const load = () => { try { return JSON.parse(readFileSync(FILE, "utf8")); } catch { return emptyPaper(cc.bankUsd ?? 100); } };
const save = (p) => { mkdirSync(new URL("./state/", import.meta.url), { recursive: true }); writeFileSync(FILE, JSON.stringify(p)); };

async function get(path) {
  for (let i = 0; i < 3; i++) {
    const r = await fetch(`https://api.skinport.com/v1/${path}`, { headers: { "accept-encoding": "br", accept: "application/json" } });
    if (r.ok) return r.json();
    if (r.status !== 429 && r.status < 500) throw new Error(`Skinport ${path}: HTTP ${r.status}`);
    await new Promise((ok) => setTimeout(ok, 60e3));
  }
  throw new Error(`Skinport ${path}: 応答なし`);
}

async function discord(text) {
  if (!env.SORARE_DISCORD_WEBHOOK) return;
  for (let i = 0; i < text.length; i += 1990) {
    const r = await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content: text.slice(i, i + 1990) }) });
    if (!r.ok) console.error(`Discord 送信失敗 HTTP ${r.status}`);
  }
}

async function main() {
  if (cc.enabled === false) return console.log("CS2 の模擬売買は止めてある(config.cs2.enabled)");
  const paper = load();
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);   // 日本時間の日付
  if (paper.lastDay === today && !env.SORARE_FORCE) return console.log(`CS2 の模擬売買は今日(${today})済み`);

  const q = "app_id=730&currency=USD";
  const market = joinMarket(await get(`items?${q}&tradable=0`), await get(`sales/history?${q}`));
  console.log(`CS2: ${market.length} 品の相場を読んだ`);

  const now = Date.now();
  const prices = Object.fromEntries(market.map((c) => [c.id, sellRef(c)]));
  let next = step(paper, prices, now, cc);
  const sold = next.closed.slice(paper.closed.length);
  const picks = pickItems(market, next.open, { ...cc, maxPrice: Math.min(cc.maxPrice ?? 15, next.cash), closed: next.closed, now });
  const r = buy(next, picks.map((c) => ({ ...c, sport: "cs2" })), now);
  next = { ...r.paper, lastDay: today };
  save(next);

  const s = summary(next, cc.feePct ?? 8);
  const lines = [`**CS2 スキンの模擬売買**(お金は動かしていません) ${today}`,
    `資産 $${s.total.toFixed(2)}(始め $${next.start} から ${s.pct >= 0 ? "+" : ""}${s.pct}%)・現金 $${next.cash.toFixed(2)}・確定した損益 ${s.realized >= 0 ? "+" : ""}$${s.realized.toFixed(2)}(${s.wins} 勝 ${s.losses} 敗)`];
  if (sold.length) lines.push("", "**仮に売った**", ...sold.map((c) => `- ${c.name}: $${c.buy.toFixed(2)} → 手取り $${c.sell.toFixed(2)}(${c.pnl >= 0 ? "+" : ""}$${c.pnl.toFixed(2)}・${c.why})`));
  if (r.bought.length) lines.push("", "**仮に買った**(上昇 = 7 日の中央値 ÷ 30 日の中央値)", ...r.bought.map((p) => `- ${p.name} $${p.buy.toFixed(2)}(上昇 ×${p.ratio})\n  <${p.card}>`));
  if (next.open.length) lines.push("", "**持っている(仮)**", ...next.open.map((p) => `- ${p.name}: 買値 $${p.buy.toFixed(2)} → 今 $${(p.last ?? p.buy).toFixed(2)}`));
  // Sorare の模擬売買(paper.js が先に動く)とくらべる
  let sorare = null;
  try { sorare = JSON.parse(readFileSync(new URL("./state/paper.json", import.meta.url), "utf8")); } catch { /* まだ無い */ }
  lines.push("", compareText([{ name: "Sorare", paper: sorare, feePct: cfg.paper?.feePct ?? 5 }, { name: "CS2", paper: next, feePct: cc.feePct ?? 8 }], now));
  const text = lines.join("\n");
  console.log(text);
  await discord(text);
}

main().catch(async (e) => { console.error(e); await discord(`⚠️ CS2 の模擬売買でエラー: ${String(e.message).slice(0, 500)}`); process.exitCode = 1; });
