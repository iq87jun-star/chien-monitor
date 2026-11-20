// ゲームのアイテムの模擬売買(お金は動かさない)。1 日 1 回、ゲームごとに Skinport の相場(鍵なし)を読み、上昇中でよく売れている品を仮に買い、
// 持っている仮の品を値洗いして決まりに沿って仮に売る。結果を Discord に送る。
// ゲームの一覧は config.json の items、決まりは cs2(既定値。ゲームごとに items の中で上書きできる)。記録は state/items-<ゲーム>.json。
// Skinport は 5 分に 8 回までなので、呼ぶ間を SKINPORT_GAP_MS(既定 40 秒)あける。
// 手元で確かめる時は SKINPORT_FIXTURE_DIR に <appId>-items.json と <appId>-history.json を置くと、fetch の代わりにそれを読む。
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { emptyPaper, step, buy, summary, compareText } from "./src/paper.js";
import { joinMarket, sellRef, pickItems, gameList, throttle } from "./src/cs2.js";

const env = process.env;
const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url), "utf8"));
const STATE = new URL("./state/", import.meta.url);
const readJson = (url) => { try { return JSON.parse(readFileSync(url, "utf8")); } catch { return null; } };
const load = (g) => readJson(new URL(g.file, STATE))
  ?? (g.legacyState && readJson(new URL(g.legacyState, STATE)))   // 前の記録(CS2 の state/cs2.json)を引き継ぐ
  ?? emptyPaper(g.bankUsd ?? 100);
const save = (g, p) => { mkdirSync(STATE, { recursive: true }); writeFileSync(new URL(g.file, STATE), JSON.stringify(p)); };

const wait = throttle(Number(env.SKINPORT_GAP_MS ?? 40e3));
async function get(appId, kind) {
  if (env.SKINPORT_FIXTURE_DIR) return JSON.parse(readFileSync(`${env.SKINPORT_FIXTURE_DIR}/${appId}-${kind}.json`, "utf8"));
  const path = kind === "items" ? `items?app_id=${appId}&currency=USD&tradable=0` : `sales/history?app_id=${appId}&currency=USD`;
  for (let i = 0; i < 3; i++) {
    await wait();
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

// 1 ゲーム分の 1 日: 値洗い → 仮に売る → 仮に買う。通知の行を返す
async function runGame(g, paper, today, now) {
  const market = joinMarket(await get(g.appId, "items"), await get(g.appId, "history"));
  const prices = Object.fromEntries(market.map((c) => [c.id, sellRef(c)]));
  let next = step(paper, prices, now, g);
  const sold = next.closed.slice(paper.closed.length);
  const picks = pickItems(market, next.open, { ...g, maxPrice: Math.min(g.maxPrice ?? 15, next.cash), closed: next.closed, now });
  const r = buy(next, picks.map((c) => ({ ...c, sport: g.key })), now);
  next = { ...r.paper, lastDay: today };
  save(g, next);
  console.log(`${g.name}: ${market.length} 品の相場を読み、${sold.length} 品を仮に売り、${r.bought.length} 品を仮に買った${r.bought.length ? `(${r.bought.map((p) => `${p.name} $${p.buy}`).join("、")})` : ""}`);

  const s = summary(next, g.feePct ?? 8);
  const lines = ["", `**${g.name}**(${market.length} 品を読んだ)`,
    `資産 $${s.total.toFixed(2)}(始め $${next.start} から ${s.pct >= 0 ? "+" : ""}${s.pct}%)・現金 $${next.cash.toFixed(2)}・確定した損益 ${s.realized >= 0 ? "+" : ""}$${s.realized.toFixed(2)}(${s.wins} 勝 ${s.losses} 敗)`];
  if (sold.length) lines.push("仮に売った:", ...sold.map((c) => `- ${c.name}: $${c.buy.toFixed(2)} → 手取り $${c.sell.toFixed(2)}(${c.pnl >= 0 ? "+" : ""}$${c.pnl.toFixed(2)}・${c.why})`));
  if (r.bought.length) lines.push("仮に買った(上昇 = 7 日の中央値 ÷ 30 日の中央値):", ...r.bought.map((p) => `- ${p.name} $${p.buy.toFixed(2)}(上昇 ×${p.ratio})\n  <${p.card}>`));
  if (next.open.length) lines.push("持っている(仮):", ...next.open.map((p) => `- ${p.name}: 買値 $${p.buy.toFixed(2)} → 今 $${(p.last ?? p.buy).toFixed(2)}`));
  return { paper: next, lines };
}

async function main() {
  const games = gameList(cfg);
  if (!games.length) return console.log("ゲームのアイテムの模擬売買は止めてある(config.cs2.enabled / items[].enabled)");
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);   // 日本時間の日付
  const now = Date.now();
  const lines = [`**ゲームのアイテムの模擬売買**(お金は動かしていません) ${today}`];
  const rows = [];
  let ran = 0, failed = 0;
  for (const g of games) {
    const paper = load(g);
    if (paper.lastDay === today && !env.SORARE_FORCE) { console.log(`${g.name} の模擬売買は今日(${today})済み`); rows.push({ name: g.name, paper, feePct: g.feePct ?? 8 }); continue; }
    try {
      const r = await runGame(g, paper, today, now);
      lines.push(...r.lines); rows.push({ name: g.name, paper: r.paper, feePct: g.feePct ?? 8 }); ran++;
    } catch (e) {
      // 1 ゲームの失敗で他を止めない
      console.error(`${g.name}:`, e); failed++;
      lines.push("", `**${g.name}**: ⚠️ エラー ${String(e.message).slice(0, 300)}`);
      rows.push({ name: g.name, paper: paper.lastDay ? paper : null, feePct: g.feePct ?? 8 });
    }
  }
  if (!ran && !failed) return;
  // Sorare の模擬売買(paper.js が先に動く)と全部くらべる
  const sorare = readJson(new URL("paper.json", STATE));
  lines.push("", compareText([{ name: "Sorare", paper: sorare, feePct: cfg.paper?.feePct ?? 5 }, ...rows], now));
  const text = lines.join("\n");
  console.log(text);
  await discord(text);
  if (failed) process.exitCode = 1;
}

main().catch(async (e) => { console.error(e); await discord(`⚠️ ゲームのアイテムの模擬売買でエラー: ${String(e.message).slice(0, 500)}`); process.exitCode = 1; });
