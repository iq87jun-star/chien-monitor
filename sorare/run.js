// Sorare の J1 Rare 大会: 次節のラインナップを選び、(設定があれば)登録し、売り候補と一緒に Discord に送る。
// 使い方: node run.js            … 締切が runWithinHours 以内の時だけ動く(毎日 1 回動かせば各節 1 回だけ当たる)
//         SORARE_FORCE=1 node run.js … 時間に関係なく動く
// 環境変数(GitHub の Secrets): SORARE_EMAIL / SORARE_PASSWORD / SORARE_OTP_SECRET(2段階認証の秘密鍵)/ SORARE_API_KEY
//   SORARE_DISCORD_WEBHOOK … 通知先。SORARE_SUBMIT=true … ラインナップを実際に登録する(既定は提案だけ)
// 売却・出品はしない(お金が動く操作は人が行う)。
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from "node:fs";
import { createClient } from "./src/api.js";
import { upcoming, clubs, player, myCards, submitLineup } from "./src/data.js";
import { teamForm, project, bestLineup, sellCandidates } from "./src/model.js";

const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));
const env = process.env;
const POS_JA = { Goalkeeper: "GK", Defender: "DF", Midfielder: "MF", Forward: "FW" };

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k]).catch(() => null); } }));
  return out;
}

async function main() {
  const api = createClient({ apiKey: env.SORARE_API_KEY || "" });
  const lines = [];
  const { fixture, leaderboard, leaderboardSlug } = await upcoming(api.gql, cfg.leaderboard);
  const hours = (Date.parse(fixture.startDate) - Date.now()) / 3600e3;
  if (!leaderboard) return console.log(`次の節 ${fixture.slug} に ${leaderboardSlug} は無い。終了`);
  if (!env.SORARE_FORCE && (hours > cfg.runWithinHours || hours < 0.25))
    return console.log(`締切まで ${hours.toFixed(1)} 時間(${cfg.runWithinHours} 時間以内で動く)。終了`);

  if (env.SORARE_EMAIL && env.SORARE_PASSWORD) {
    const me = await api.signIn({ email: env.SORARE_EMAIL, password: env.SORARE_PASSWORD, otpSecret: env.SORARE_OTP_SECRET || "" });
    console.log(`ログイン: ${me}`);
  }

  const cl = await clubs(api.gql, cfg.competition);
  const form = Object.fromEntries(cl.map((c) => [c.name, teamForm(c.name, c.games)]));
  const next = Object.fromEntries(cl.filter((c) => c.next).map((c) => {
    const home = c.next.homeTeam.name === c.name;
    return [c.name, { opp: home ? c.next.awayTeam.name : c.next.homeTeam.name, home }];
  }));
  const avgGf = cl.reduce((s, c) => s + form[c.name].gf, 0) / cl.length;
  const ctx = { form, next, avgGf };

  // 市場の最安値の出品から、予算内で一番の組み合わせ(未ログイン時と、手持ちで 5 枚そろわない時の購入候補)
  async function market() {
    const slugs = cl.flatMap((c) => c.players);
    const ps = (await pool(slugs, 4, (s) => player(api.gql, s, cfg.rarity))).filter((p) => p && p.league === cfg.competition);
    return bestLineup(ps.map((p) => project({ ...p, card: p.priceCard }, ctx)), { maxPerClub: cfg.maxPerClub, budget: cfg.marketBudgetUsd });
  }

  let best, buying = false, owned = [];
  if (api.authed) {
    const all = await myCards(api.gql, cfg.rarity);
    const cards = all.filter((c) => c.seasonYear === cfg.seasonYear && c.player);
    const bySlug = new Map();
    for (const c of cards) if (!bySlug.has(c.player)) bySlug.set(c.player, c.slug);
    const ps = (await pool([...bySlug.keys()], 3, (s) => player(api.gql, s, cfg.rarity))).filter((p) => p && p.league === cfg.competition);
    owned = ps.map((p) => project({ ...p, card: bySlug.get(p.id), floor: p.price, price: null }, ctx));
    lines.push(`手持ちの ${cfg.rarity} カード: 全 ${all.length} 枚、うち ${cfg.seasonYear} 年の J1 選手 ${owned.length} 人`);
    best = bestLineup(owned, { maxPerClub: cfg.maxPerClub });
    if (!best) {
      lines.push("手持ちでは 5 枚そろわない(GK・DF・MF・FW が各 1 枚以上必要)。代わりに購入候補を出します");
      best = await market(); buying = true;
    }
  } else {
    lines.push(`未ログイン: 市場の最安値で予算 $${cfg.marketBudgetUsd} 以内の組み合わせを提案`);
    best = await market(); buying = true;
  }

  lines.unshift(`**Sorare ${leaderboard.displayName}(J1 ${cfg.rarity})** ${fixture.slug} 締切まで約 ${hours.toFixed(0)} 時間`);
  if (!best) {
    lines.push("5 枚そろう組み合わせが無い");
  } else {
    if (buying) lines.push(`**購入候補(予算 $${cfg.marketBudgetUsd} 以内・今の最安出品)**`);
    const slot = ["GK", "DF", "MF", "FW", "EX"];
    best.lineup.forEach((c, i) => lines.push(`${slot[i]} ${c.name}(${c.club}${c.home ? " vs " : " @ "}${c.opp})予想 ${c.proj.toFixed(0)}${c.id === best.captain ? " ★キャプテン" : ""}${c.price != null ? ` $${c.price.toFixed(2)}` : ""}`));
    lines.push(`予想合計 ${best.pts.toFixed(0)}(ボーナス抜き)${buying ? ` / 費用 $${best.cost.toFixed(2)}` : ""}`);
    if (buying) {
      lines.push("(購入はアプリで行ってください。買った後の次の実行で、手持ちから組んで登録します)");
    } else if (env.SORARE_SUBMIT === "true") {
      const cap = best.lineup.find((c) => c.id === best.captain).card;
      const id = await submitLineup(api.gql, leaderboard.id, best.lineup, cap);
      lines.push(`✅ ラインナップを登録しました(${id})`);
    } else {
      lines.push("(提案のみ。登録するには SORARE_SUBMIT=true)");
    }
  }

  if (owned.length) {
    const sell = sellCandidates(owned, cfg.sell);
    if (sell.length) {
      lines.push("", "**売却の検討候補**(出品はアプリで行ってください)");
      for (const c of sell) lines.push(`- ${c.name}(${c.club}・${POS_JA[c.pos]}): ${c.reasons.join("・")} / 今の最安出品 ${c.floor != null ? "$" + c.floor.toFixed(2) : "なし"}`);
    }
  }

  const text = lines.join("\n");
  console.log(text);
  mkdirSync(new URL("./out/", import.meta.url), { recursive: true });
  writeFileSync(new URL("./out/summary.md", import.meta.url), text + "\n");
  if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, text + "\n");
  if (env.SORARE_DISCORD_WEBHOOK) {
    const r = await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content: text.slice(0, 1990) }) });
    if (!r.ok) console.error(`Discord 送信失敗 HTTP ${r.status}`);
  }
}

main().catch(async (e) => {
  console.error(e);
  if (env.SORARE_DISCORD_WEBHOOK) {
    await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content: `⚠️ Sorare 自動化でエラー: ${String(e.message).slice(0, 1800)}` }) }).catch(() => {});
  }
  process.exit(1);
});
