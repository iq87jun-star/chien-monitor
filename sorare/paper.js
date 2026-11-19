// 模擬売買(お金は動かさない)。1 日 1 回、config の大会のリーグの Limited カードを調べて、
// 勢いのある選手を仮に買い、持っている仮のカードを値洗いして決まりに沿って仮に売る。結果を Discord に送る。
// 記録は state/paper.json(GitHub Actions のキャッシュ)。決まりは config.json の paper。
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createClient, setRates } from "./src/api.js";
import { clubs, player, nbaPlayer } from "./src/data.js";
import { emptyPaper, step, pickBuys, buy, summary } from "./src/paper.js";

const env = process.env;
const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url), "utf8"));
const pc = cfg.paper || {};
const FILE = new URL("./state/paper.json", import.meta.url);
const load = () => { try { return JSON.parse(readFileSync(FILE, "utf8")); } catch { return emptyPaper(pc.bankUsd ?? 100); } };
const save = (p) => { mkdirSync(new URL("./state/", import.meta.url), { recursive: true }); writeFileSync(FILE, JSON.stringify(p)); };

async function pool(items, n, fn) {
  const out = new Array(items.length); let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k]).catch(() => null); } }));
  return out;
}

async function discord(text) {
  if (!env.SORARE_DISCORD_WEBHOOK) return;
  for (let i = 0; i < text.length; i += 1990) {
    const r = await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content: text.slice(i, i + 1990) }) });
    if (!r.ok) console.error(`Discord 送信失敗 HTTP ${r.status}`);
  }
}

async function main() {
  if (pc.enabled === false) return console.log("模擬売買は止めてある(config.paper.enabled)");
  const paper = load();
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);   // 日本時間の日付
  if (paper.lastDay === today && !env.SORARE_FORCE) return console.log(`模擬売買は今日(${today})済み`);

  const api = createClient({ apiKey: env.SORARE_API_KEY || "" });
  try { setRates((await api.gql("{ config { exchangeRate { rates } } }")).config.exchangeRate.rates); } catch { /* ユーロ 1.1 */ }

  // 調べるリーグ: 有効な大会のリーグ(同じリーグは 1 回)。Limited の最安出品で売買する
  const leagues = new Map();
  for (const t of (cfg.targets || []).filter((t) => t.enabled !== false)) leagues.set(t.competition, t.sport === "nba" ? "nba" : "football");
  const cands = [];
  for (const [competition, sport] of leagues) {
    const cl = await clubs(api.gql, competition);
    const get = sport === "nba" ? (s) => nbaPlayer(api.gql, s, "limited") : (s) => player(api.gql, s, "limited");
    const ps = (await pool(cl.flatMap((c) => c.players), 4, get)).filter((p) => p && p.league === competition);
    for (const p of ps) cands.push({ ...p, sport, card: p.priceCard });
    console.log(`${competition}: ${ps.length} 人を調べた`);
  }

  const now = Date.now();
  const prices = Object.fromEntries(cands.filter((c) => c.price != null).map((c) => [c.id, c.price]));
  let next = step(paper, prices, now, pc);
  const sold = next.closed.slice(paper.closed.length);
  const picks = pickBuys(cands, next.open, { ...pc, maxPrice: Math.min(pc.maxPrice ?? 15, next.cash), closed: next.closed, now });
  const r = buy(next, picks, now);
  next = { ...r.paper, lastDay: today };
  save(next);

  const s = summary(next, pc.feePct ?? 5);
  const url = (p) => `https://sorare.com/${p.sport === "nba" ? "nba" : "football"}/cards/${p.card}`;
  const lines = [`**模擬売買**(お金は動かしていません) ${today}`,
    `資産 $${s.total.toFixed(2)}(始め $${next.start} から ${s.pct >= 0 ? "+" : ""}${s.pct}%)・現金 $${next.cash.toFixed(2)}・確定した損益 ${s.realized >= 0 ? "+" : ""}$${s.realized.toFixed(2)}(${s.wins} 勝 ${s.losses} 敗)`];
  if (sold.length) lines.push("", "**仮に売った**", ...sold.map((c) => `- ${c.name}: $${c.buy.toFixed(2)} → 手取り $${c.sell.toFixed(2)}(${c.pnl >= 0 ? "+" : ""}$${c.pnl.toFixed(2)}・${c.why})`));
  if (r.bought.length) lines.push("", "**仮に買った**(勢い = 直近3試合 ÷ 直近10試合)", ...r.bought.map((p) => `- ${p.name} $${p.buy.toFixed(2)}(勢い ×${p.ratio})\n  <${url(p)}>`));
  if (next.open.length) lines.push("", "**持っている(仮)**", ...next.open.map((p) => `- ${p.name}: 買値 $${p.buy.toFixed(2)} → 今 $${(p.last ?? p.buy).toFixed(2)}`));
  const text = lines.join("\n");
  console.log(text);
  await discord(text);
}

main().catch(async (e) => { console.error(e); await discord(`⚠️ 模擬売買でエラー: ${String(e.message).slice(0, 500)}`); process.exitCode = 1; });
