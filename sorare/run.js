// Sorare の大会(config.targets。既定は J1 Rare): 次節のラインナップを選び、(設定があれば)登録し、売り候補と一緒に Discord に送る。
// 使い方: node run.js            … 締切が runWithinHours 以内の時だけ動く(毎日 1 回動かせば各節 1 回だけ当たる)
//         SORARE_FORCE=1 node run.js … 時間に関係なく動く
//         SORARE_FIXTURE=football-6-10-nov-2026 … 次の節の代わりにその節で動く(先の節を試す時用)
// 環境変数(GitHub の Secrets): SORARE_EMAIL / SORARE_PASSWORD / SORARE_OTP_SECRET(2段階認証の秘密鍵)/ SORARE_API_KEY
//   SORARE_DISCORD_WEBHOOK … 通知先。SORARE_SUBMIT=true … ラインナップを実際に登録する(既定は提案だけ)
// 購入・出品は SORARE_TRADE=true と SORARE_PRIVATE_KEY(ウォレットの秘密鍵)がある時だけ、config の trade の上限内で行う。
// それ以外は「購入予定・出品予定」をリンク付きで送るだけ(試し運転)。
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from "node:fs";
import { createClient, setRates } from "./src/api.js";
import { upcoming, clubs, player, myCards, submitLineup } from "./src/data.js";
import { teamForm, project, bestLineup, sellCandidates, sellPrice } from "./src/model.js";
import { createTrader, planBuys, planSells, spentInWeek } from "./src/trade.js";

const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));
const env = process.env;
const POS_JA = { Goalkeeper: "GK", Defender: "DF", Midfielder: "MF", Forward: "FW" };
const SLOT = ["GK", "DF", "MF", "FW", "EX"];
const cardUrl = (slug) => `https://sorare.com/football/cards/${slug}`;

// Discord の 1 通 2000 文字に収まるよう、行の区切りで分ける
function chunks(text, max) {
  const out = [""];
  for (const line of text.split("\n")) {
    if (out[out.length - 1].length + line.length + 1 > max) out.push("");
    out[out.length - 1] += (out[out.length - 1] ? "\n" : "") + line.slice(0, max);
  }
  return out.filter(Boolean);
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k]).catch(() => null); } }));
  return out;
}

// config.targets の大会ごとに runTarget を順に動かす。ログイン・換算レート・自動購入の週の上限は全大会で共通
async function main() {
  const api = createClient({ apiKey: env.SORARE_API_KEY || "" });
  const targets = (cfg.targets || [{}]).filter((t) => t.enabled !== false).map((t) => ({ ...cfg, ...t }));
  const { fixture } = await upcoming(api.gql, targets[0].leaderboard);
  const hours = (Date.parse(fixture.startDate) - Date.now()) / 3600e3;
  if (!env.SORARE_FORCE && (hours > cfg.runWithinHours || hours < 0.25))
    return console.log(`締切まで ${hours.toFixed(1)} 時間(${cfg.runWithinHours} 時間以内で動く)。終了`);

  if (env.SORARE_EMAIL && env.SORARE_PASSWORD) {
    const me = await api.signIn({ email: env.SORARE_EMAIL, password: env.SORARE_PASSWORD, otpSecret: env.SORARE_OTP_SECRET || "" });
    console.log(`ログイン: ${me}`);
  }

  // ユーロ・ETH の換算レート(ETH 建ての出品を USD で比べるため)
  try { setRates((await api.gql("{ config { exchangeRate { rates } } }")).config.exchangeRate.rates); } catch { /* 読めなければユーロ 1.1・ETH は換算しない */ }

  // 直近 7 日の購入額は、全大会のランクの手持ちから数え、この実行で買った分を足していく
  const shared = { spent: null };
  if (api.authed) {
    shared.spent = 0;
    for (const r of new Set(targets.map((t) => t.rarity))) shared.spent += spentInWeek(await myCards(api.gql, r));
  }

  mkdirSync(new URL("./out/", import.meta.url), { recursive: true });
  writeFileSync(new URL("./out/summary.md", import.meta.url), "");
  let failed = false;
  for (const t of targets) {
    let text;
    try { text = await runTarget(api, t, shared); }
    catch (e) { console.error(e); failed = true; text = `⚠️ Sorare 自動化でエラー(${t.name}): ${String(e.message).slice(0, 1800)}`; }
    if (!text) continue;
    console.log(text);
    appendFileSync(new URL("./out/summary.md", import.meta.url), text + "\n\n");
    if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, text + "\n\n");
    if (env.SORARE_DISCORD_WEBHOOK) {
      for (const content of chunks(text, 1990)) {
        const r = await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content }) });
        if (!r.ok) console.error(`Discord 送信失敗 HTTP ${r.status}`);
      }
    }
  }
  if (failed) process.exitCode = 1;
}

// 1 つの大会(t = config の既定値に targets の 1 件を重ねたもの)のラインナップ・購入・売却。通知の本文を返す
async function runTarget(api, t, shared) {
  const lines = [];
  const { fixture, leaderboard, leaderboardSlug } = await upcoming(api.gql, t.leaderboard);
  const hours = (Date.parse(fixture.startDate) - Date.now()) / 3600e3;
  if (!leaderboard) { console.log(`次の節 ${fixture.slug} に ${leaderboardSlug} は無い(${t.name})`); return null; }

  const cl = await clubs(api.gql, t.competition);
  const form = Object.fromEntries(cl.map((c) => [c.name, teamForm(c.name, c.games)]));
  const next = Object.fromEntries(cl.filter((c) => c.next).map((c) => {
    const home = c.next.homeTeam.name === c.name;
    return [c.name, { opp: home ? c.next.awayTeam.name : c.next.homeTeam.name, home }];
  }));
  const avgGf = cl.reduce((s, c) => s + form[c.name].gf, 0) / cl.length;
  const ctx = { form, next, avgGf };

  // 購入候補(未ログイン時と、手持ちで 5 枚そろわない時): 市場の最安出品から「最安」(予算 marketBudgetUsd)と
  // 「プラスアルファ」(予算 plusBudgetUsd。最安より予想が高い時だけ)の 2 案
  async function market() {
    const slugs = cl.flatMap((c) => c.players);
    const ps = (await pool(slugs, 4, (s) => player(api.gql, s, t.rarity))).filter((p) => p && p.league === t.competition);
    const cands = ps.map((p) => project({ ...p, card: p.priceCard }, ctx));
    const cheap = bestLineup(cands, { maxPerClub: t.maxPerClub, budget: t.marketBudgetUsd });
    const plus = bestLineup(cands, { maxPerClub: t.maxPerClub, budget: t.plusBudgetUsd });
    return [cheap && { title: `最安プラン(予算 $${t.marketBudgetUsd} 以内)`, ...cheap },
      plus && (!cheap || plus.pts > cheap.pts + 0.5) && { title: `プラスアルファ プラン(予算 $${t.plusBudgetUsd} 以内)`, ...plus }].filter(Boolean);
  }
  const lineupLines = (b, links) => b.lineup.map((c, i) => `${SLOT[i]} ${c.name}(${c.club}${c.home ? " vs " : " @ "}${c.opp})予想 ${c.proj.toFixed(0)}${c.id === b.captain ? " ★キャプテン" : ""}${c.price != null ? ` $${c.price.toFixed(2)}` : ""}${links && c.card ? `\n  <${cardUrl(c.card)}>` : ""}`);

  // 手持ち(seasonYear 年の、この大会のリーグの選手)を読み直す。自動購入の後にも呼ぶ
  let all = [], owned = [];
  async function loadOwned() {
    all = await myCards(api.gql, t.rarity);
    const bySlug = new Map();
    for (const c of all) if (c.seasonYear === t.seasonYear && c.player && !bySlug.has(c.player)) bySlug.set(c.player, c);
    const ps = (await pool([...bySlug.keys()], 3, (s) => player(api.gql, s, t.rarity))).filter((p) => p && p.league === t.competition);
    owned = ps.map((p) => { const c = bySlug.get(p.id); return project({ ...p, card: c.slug, cost: c.cost, since: c.since, floor: p.price, price: null }, ctx); });
    return bestLineup(owned, { maxPerClub: t.maxPerClub });
  }

  const tr = cfg.trade;
  const trading = api.authed && env.SORARE_TRADE === "true" && !!env.SORARE_PRIVATE_KEY;
  const trader = trading ? createTrader(api.gql, { privateKey: env.SORARE_PRIVATE_KEY, currency: tr.currency }) : null;
  const tradeNote = trading ? "" : "(試し運転: 実行はしない。実行するには SORARE_TRADE=true と SORARE_PRIVATE_KEY)";

  let best = null, plans = [];
  if (api.authed) {
    best = await loadOwned();
    lines.push(`手持ちの ${t.rarity} カード: 全 ${all.length} 枚、うち ${t.seasonYear} 年の ${t.league} の選手 ${owned.length} 人`);
    if (!best) {
      lines.push("手持ちでは 5 枚そろわない(GK・DF・MF・FW が各 1 枚以上必要)。代わりに購入候補を出します");
      plans = await market();
    }
  } else {
    lines.push("未ログイン: 購入候補を出します");
    plans = await market();
  }

  lines.unshift(`**Sorare ${t.name}(${leaderboard.displayName})** ${fixture.slug} 締切まで約 ${hours.toFixed(0)} 時間`);
  for (const pl of plans) {
    lines.push("", `**購入候補: ${pl.title}**(今の最安出品)`, ...lineupLines(pl, true),
      `予想合計 ${pl.pts.toFixed(0)}(ボーナス抜き) / 費用 $${pl.cost.toFixed(2)}`);
  }
  if (plans.length === 2) lines.push(`→ プラスアルファは +$${(plans[1].cost - plans[0].cost).toFixed(2)} で予想 +${(plans[1].pts - plans[0].pts).toFixed(0)} 点`);

  // 自動購入: buyPlan のプランを、1 枚と週の上限の範囲で買う。手持ちにある選手は買わない
  const plan = plans.find((p) => p.title.startsWith(tr.buyPlan === "plus" ? "プラスアルファ" : "最安")) || plans[0];
  if (plan && api.authed) {
    const have = new Set(owned.map((c) => c.id));
    const buys = planBuys(plan.lineup.filter((c) => !have.has(c.id)), tr, shared.spent ?? spentInWeek(all));
    lines.push("", `**自動購入**(${plan.title}・1枚 $${tr.perCardMaxUsd}・週 $${tr.weeklyMaxUsd} まで)${tradeNote}`);
    let bought = 0;
    for (const b of buys) {
      if (!b.ok) { lines.push(`- 見送り ${b.name} $${b.price?.toFixed(2)}: ${b.why}`); continue; }
      if (!trading) { lines.push(`- 購入予定 ${b.name} $${b.price.toFixed(2)}`); continue; }
      try { const paid = await trader.buy(b.card, b.price); bought++; shared.spent += paid; lines.push(`- ✅ 購入 ${b.name} $${paid.toFixed(2)}`); }
      catch (e) { lines.push(`- ⚠️ 購入できず ${b.name}: ${e.message}`); }
    }
    if (bought) {
      best = await loadOwned();
      lines.push(best ? "手持ちで 5 枚そろったので、このまま組みます" : "まだ 5 枚そろわない(次の実行で続きを買います)");
    }
  } else if (plans.length) {
    lines.push("(買った後の次の実行で、手持ちから組んで登録します)");
  }

  if (!best && !plans.length) lines.push("5 枚そろう組み合わせが無い");
  if (best) {
    lines.push("", "**ラインナップ**", ...lineupLines(best, false), `予想合計 ${best.pts.toFixed(0)}(ボーナス抜き)`);
    if (env.SORARE_SUBMIT === "true") {
      const cap = best.lineup.find((c) => c.id === best.captain).card;
      const id = await submitLineup(api.gql, leaderboard.id, best.lineup, cap);
      lines.push(`✅ ラインナップを登録しました(${id})`);
    } else {
      lines.push("(提案のみ。登録するには SORARE_SUBMIT=true)");
    }
  }

  // 売却候補: 条件に当てはまるカードを、ラインナップ・保有期間・買値を確かめてから出品する
  if (owned.length) {
    const sell = sellCandidates(owned, cfg.sell).map((c) => ({ ...c, ask: sellPrice(c.floor, cfg.sell.undercutPct) }));
    if (sell.length) {
      lines.push("", `**売却候補**(条件: ${cfg.sell.maxAge + 1}歳以上、スタメン率 ${Math.round(cfg.sell.minStartRate * 100)}% 未満、または買値から +${cfg.sell.gainPct}% 以上の値上がり)${tradeNote}`);
      const inLineup = new Set(best ? best.lineup.map((c) => c.card) : []);
      for (const c of planSells(sell, tr, inLineup)) {
        const head = `- ${c.name}(${c.club}・${POS_JA[c.pos]}): ${c.reasons.join("・")} / 今の最安出品 ${c.floor != null ? "$" + c.floor.toFixed(2) : "なし"}`;
        if (!c.ok) { lines.push(`${head} / 見送り: ${c.why}\n  <${cardUrl(c.card)}>`); continue; }
        if (!trading) { lines.push(`${head} / 出品予定 $${c.price.toFixed(2)}\n  <${cardUrl(c.card)}>`); continue; }
        try { const listed = await trader.list(c.card, c.price); lines.push(`${head} / ✅ 出品 $${listed.toFixed(2)}\n  <${cardUrl(c.card)}>`); }
        catch (e) { lines.push(`${head} / ⚠️ 出品できず: ${e.message}\n  <${cardUrl(c.card)}>`); }
      }
    }
  }

  return lines.join("\n");
}

main().catch(async (e) => {
  console.error(e);
  if (env.SORARE_DISCORD_WEBHOOK) {
    await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content: `⚠️ Sorare 自動化でエラー: ${String(e.message).slice(0, 1800)}` }) }).catch(() => {});
  }
  process.exit(1);
});
