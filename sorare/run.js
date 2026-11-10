// Sorare の大会(config.targets。既定は J1 Rare): 次節のラインナップを選び、(設定があれば)登録し、売り候補と一緒に Discord に送る。
// 使い方: node run.js            … 締切が runWithinHours 以内の時だけ動く(毎日 1 回動かせば各節 1 回だけ当たる)
//         SORARE_FORCE=1 node run.js … 時間に関係なく動く
//         SORARE_FIXTURE=football-6-10-nov-2026 … 次の節の代わりにその節で動く(先の節を試す時用)
// 環境変数(GitHub の Secrets): SORARE_EMAIL / SORARE_PASSWORD / SORARE_OTP_SECRET(2段階認証の秘密鍵)/ SORARE_API_KEY
//   SORARE_DISCORD_WEBHOOK … 通知先。SORARE_SUBMIT=true … ラインナップを実際に登録する(既定は提案だけ)
// 購入・出品は SORARE_TRADE=true と SORARE_PRIVATE_KEY(ウォレットの秘密鍵)がある時だけ、config の trade の上限内で行う。
// それ以外は「購入予定・出品予定」をリンク付きで送るだけ(試し運転)。
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from "node:fs";
import { createClient, setRates, usd } from "./src/api.js";
import { market, walletUsd, leaderboardCutoff, fixtureScore, upcoming, pastFixture, fixtureResults, clubs, player, nbaPlayer, fixtureGames, nbaStars, myCards, submitLineup } from "./src/data.js";
import { teamForm, project, bestLineup, nbaProject, bestNbaLineup, sellCandidates, sellPrice, swapCandidates, resultText } from "./src/model.js";
import { createTrader, planBuys, planSells, spentInWeek, pickPlan } from "./src/trade.js";
import { emptyLearn, calibration, cutoffLine, reach, sellSignal, addPrice, cashRank } from "./src/learn.js";

const cfg = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));
const env = process.env;
const POS_JA = { Goalkeeper: "GK", Defender: "DF", Midfielder: "MF", Forward: "FW", guard: "G", forward: "F", center: "C" };
const SLOT = ["GK", "DF", "MF", "FW", "EX"];
const sportOf = (t) => (t.sport === "nba" ? "NBA" : "FOOTBALL");
const cardUrl = (slug, t) => `https://sorare.com/${t.sport === "nba" ? "nba" : "football"}/cards/${slug}`;

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
// 済んだ大会の記録(節の slug:大会名)。GitHub Actions のキャッシュで実行をまたいで残す(リポジトリには書かない)。
// 定期実行は 1 日に何回も動くので、その節で済んだ大会は 2 回目から何もしない(通知も送らない)
const STATE = new URL("./state/done.json", import.meta.url);

async function discord(text) {
  if (!env.SORARE_DISCORD_WEBHOOK) return;
  for (const content of chunks(text, 1990)) {
    const r = await fetch(env.SORARE_DISCORD_WEBHOOK, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content }) });
    if (!r.ok) console.error(`Discord 送信失敗 HTTP ${r.status}`);
  }
}
const LEARN = new URL("./state/learn.json", import.meta.url);
function loadLearn() { try { return { ...emptyLearn(), ...JSON.parse(readFileSync(LEARN, "utf8")) }; } catch { return emptyLearn(); } }
function saveLearn(l) { mkdirSync(new URL("./state/", import.meta.url), { recursive: true }); l.samples = l.samples.slice(-3000); writeFileSync(LEARN, JSON.stringify(l)); }

// 終わった節から学ぶ: 各大会の入賞ライン(全大会、出ていなくても)と、予想した選手の実際の点数(サッカー)
async function learnFromFixture(api, learn, slug, sport) {
  const notes = [];
  for (const t of (cfg.targets || []).filter((t) => t.enabled !== false && sportOf(t) === sport)) {
    const c = await leaderboardCutoff(api.gql, `${slug}-${t.leaderboard}`, cashRank);
    if (!c) continue;
    (learn.cutoffs[t.name] ||= []).push({ fixture: slug, ...c });
    learn.cutoffs[t.name] = learn.cutoffs[t.name].slice(-20);
    notes.push(`${t.name}: 賞金は ${c.rank} 位まで、${c.rank} 位は ${c.score.toFixed(1)} 点(${c.teams} チーム)`);
  }
  const pend = learn.pending[slug];
  if (pend && sport === "FOOTBALL") {
    let n = 0;
    for (const [player, [pos, proj]] of Object.entries(pend.players)) {
      try { const actual = await fixtureScore(api.gql, player, slug); if (actual != null) { learn.samples.push({ pos, proj, actual }); n++; } } catch { /* 読めない選手は飛ばす */ }
    }
    notes.push(`予想と実際の点数を ${n} 人分記録(予想の補正に使う)`);
  }
  delete learn.pending[slug];
  saveLearn(learn);
  return notes;
}

function loadDone() { try { return JSON.parse(readFileSync(STATE, "utf8")); } catch { return []; } }
function saveDone(done) { mkdirSync(new URL("./state/", import.meta.url), { recursive: true }); writeFileSync(STATE, JSON.stringify(done.slice(-100))); }

async function main() {
  const api = createClient({ apiKey: env.SORARE_API_KEY || "" });
  // 締切(節の開始)が runWithinHours 以内の大会だけ動かす。競技ごとに節の日程が違うので大会ごとに見る
  const targets = [];
  const done = loadDone();
  saveDone(done);   // キャッシュに保存するファイルを、何もしない日にも作っておく
  for (const t of (cfg.targets || [{}]).filter((t) => t.enabled !== false).map((t) => ({ ...cfg, ...t }))) {
    const { fixture } = await upcoming(api.gql, t.leaderboard, sportOf(t));
    const hours = (Date.parse(fixture.startDate) - Date.now()) / 3600e3;
    t.doneKey = `${fixture.slug}:${t.name}`;
    if (!env.SORARE_FORCE && done.includes(t.doneKey)) console.log(`${t.name}: ${fixture.slug} は済んでいる`);
    else if (env.SORARE_FORCE || (hours <= cfg.runWithinHours && hours >= 0.25)) targets.push(t);
    else console.log(`${t.name}: ${fixture.slug} の締切まで ${hours.toFixed(1)} 時間(${cfg.runWithinHours} 時間以内で動く)`);
  }
  // 終わった節の結果(順位・点数・賞金)を、確定(closed)した後の最初の実行で 1 回だけ送る
  const results = [];
  for (const sport of new Set((cfg.targets || []).filter((t) => t.enabled !== false).map(sportOf))) {
    const fx = await pastFixture(api.gql, sport);
    if (fx?.aasmState === "closed" && !done.includes(`result:${fx.slug}`)) results.push(fx.slug);
  }
  if (!targets.length && !results.length) return console.log("今日動く大会も、送る結果も無い。終了");

  if (env.SORARE_EMAIL && env.SORARE_PASSWORD) {
    const me = await api.signIn({ email: env.SORARE_EMAIL, password: env.SORARE_PASSWORD, otpSecret: env.SORARE_OTP_SECRET || "" });
    console.log(`ログイン: ${me}`);
    market.currency = cfg.trade?.currency || null;   // 価格は、この通貨で買える出品の最安にする
  }

  // ユーロ・ETH の換算レート(ETH 建ての出品を USD で比べるため)
  try { setRates((await api.gql("{ config { exchangeRate { rates } } }")).config.exchangeRate.rates); } catch { /* 読めなければユーロ 1.1・ETH は換算しない */ }

  const learn = loadLearn();
  for (const slug of api.authed ? results : []) {
    try {
      const notes = await learnFromFixture(api, learn, slug, slug.startsWith("nba-") ? "NBA" : "FOOTBALL");
      const text = resultText(await fixtureResults(api.gql, slug), usd);
      const full = text && [text, "", "**学習(入賞ライン)**", ...notes.map((x) => "- " + x)].join("\n");
      if (full) { console.log(full); await discord(full); }
      else console.log(`${slug}: この節には出ていない / ${notes.join(" / ")}`);
      done.push(`result:${slug}`); saveDone(done);
    } catch (e) { console.error(`${slug} の結果を読めない: ${e.message}`); }
  }
  if (!targets.length) return;

  // 直近 7 日の購入額は、全大会のランクの手持ちから数え、この実行で買った分を足していく
  // 残高: 自動購入はこの範囲だけ(賞金・売却で増えたら、config の targets の順に広がる)。購入するたびに減らしていく
  const shared = { spent: null, balance: null, learn };
  if (api.authed) {
    shared.balance = await walletUsd(api.gql);
    console.log(`ウォレット残高: ${shared.balance != null ? "$" + shared.balance.toFixed(2) : "読めない"}`);
    shared.spent = 0;
    for (const k of new Set(targets.map((t) => `${t.rarity}:${sportOf(t)}`))) shared.spent += spentInWeek(await myCards(api.gql, ...k.split(":")));
  }

  mkdirSync(new URL("./out/", import.meta.url), { recursive: true });
  writeFileSync(new URL("./out/summary.md", import.meta.url), "");
  let failed = false;
  for (const t of targets) {
    let text;
    try {
      text = await runTarget(api, t, shared);
      // 自動購入で 5 枚そろわなかった時は済みにしない(次の実行で買い直す)。エラーの時も同じ
      if (!t.retry && !done.includes(t.doneKey)) { done.push(t.doneKey); saveDone(done); }
      saveLearn(learn);
    }
    catch (e) { console.error(e); failed = true; text = `⚠️ Sorare 自動化でエラー(${t.name}): ${String(e.message).slice(0, 1800)}`; }
    if (!text) continue;
    console.log(text);
    appendFileSync(new URL("./out/summary.md", import.meta.url), text + "\n\n");
    if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, text + "\n\n");
    await discord(text);
  }
  if (failed) process.exitCode = 1;
}

// 1 つの大会(t = config の既定値に targets の 1 件を重ねたもの)のラインナップ・購入・売却。通知の本文を返す
async function runTarget(api, t, shared) {
  const lines = [];
  const nba = t.sport === "nba";
  const { fixture, leaderboard, leaderboardSlug } = await upcoming(api.gql, t.leaderboard, sportOf(t));
  const hours = (Date.parse(fixture.startDate) - Date.now()) / 3600e3;
  if (!leaderboard) { console.log(`次の節 ${fixture.slug} に ${leaderboardSlug} は無い(${t.name})`); return null; }

  // 競技ごとの違い: 選手の取り方(getPlayer)、予想(proj)、組み合わせの選び方(optimize)
  const cl = await clubs(api.gql, t.competition);
  let getPlayer, proj, optimize;
  if (nba) {
    const games = await fixtureGames(api.gql, fixture.slug), stars = await nbaStars(api.gql);
    const starCap = leaderboard.rules?.averageScores?.max ?? Infinity;
    getPlayer = (s) => nbaPlayer(api.gql, s, t.rarity);
    proj = (p) => nbaProject({ ...p, stars: stars[p.tier] ?? null }, games);
    optimize = (c, o = {}) => bestNbaLineup(c, { starCap, budget: o.budget ?? Infinity });
  } else {
    const form = Object.fromEntries(cl.map((c) => [c.name, teamForm(c.name, c.games)]));
    const next = Object.fromEntries(cl.filter((c) => c.next).map((c) => {
      const home = c.next.homeTeam.name === c.name;
      return [c.name, { opp: home ? c.next.awayTeam.name : c.next.homeTeam.name, home }];
    }));
    const avgGf = cl.reduce((s, c) => s + form[c.name].gf, 0) / cl.length;
    getPlayer = (s) => player(api.gql, s, t.rarity);
    // 過去の節の「実際 ÷ 予想」で、ポジションごとに補正する(記録が少ないうちはほぼ 1)
    proj = (p) => { const r = project(p, { form, next, avgGf }); return { ...r, proj: r.proj * calibration(shared.learn.samples, p.pos) }; };
    optimize = (c, o = {}) => bestLineup(c, { maxPerClub: t.maxPerClub, budget: o.budget ?? Infinity });
  }

  // 購入候補(未ログイン時と、手持ちで 5 枚そろわない時): 市場の最安出品から「最安」(予算 marketBudgetUsd)と
  // 「プラスアルファ」(予算 plusBudgetUsd。最安より予想が高い時だけ)の 2 案
  let mktCache = null;
  async function marketCands() {
    if (!mktCache) {
      const slugs = cl.flatMap((c) => c.players);
      const ps = (await pool(slugs, 4, getPlayer)).filter((p) => p && p.league === t.competition);
      mktCache = ps.map((p) => proj({ ...p, card: p.priceCard }));
    }
    return mktCache;
  }
  async function market() {
    // 手持ちの選手は価格 0(手持ちのカードを使う)にして、足りない分だけ買う組み合わせを選ぶ
    const mine = new Map(owned.map((c) => [c.id, c]));
    const mkt = await marketCands();
    const cands = [...mkt.map((p) => (mine.has(p.id) ? { ...mine.get(p.id), price: 0, owned: true } : p)),
      ...owned.filter((c) => !mkt.some((p) => p.id === c.id)).map((c) => ({ ...c, price: 0, owned: true }))];
    const cheap = optimize(cands, { budget: t.marketBudgetUsd });
    const plus = optimize(cands, { budget: t.plusBudgetUsd });
    return [cheap && { title: `最安プラン(予算 $${t.marketBudgetUsd} 以内)`, ...cheap },
      plus && (!cheap || plus.pts > cheap.pts + 0.5) && { title: `プラスアルファ プラン(予算 $${t.plusBudgetUsd} 以内)`, ...plus }].filter(Boolean);
  }
  const where = (c) => (nba ? `${c.club}・節に ${c.games} 試合・★${c.stars}${c.injury ? `・${c.injury}` : ""}` : `${c.club}${c.home ? " vs " : " @ "}${c.opp}`);
  const lineupLines = (b, links) => [...b.lineup.map((c, i) => `${nba ? POS_JA[c.pos] || "P" : SLOT[i]} ${c.name}(${where(c)})予想 ${c.proj.toFixed(0)}${c.id === b.captain ? " ★キャプテン" : ""}${c.owned ? " 手持ち" : c.price != null ? ` $${c.price.toFixed(2)}` : ""}${links && c.card && !c.owned ? `\n  <${cardUrl(c.card, t)}>` : ""}`),
    ...(nba && b.stars != null ? [`星の合計 ${b.stars} / 上限 ${leaderboard.rules?.averageScores?.max ?? "なし"}`] : [])];

  // 手持ち(seasonYear 年の、この大会のリーグの選手)を読み直す。自動購入の後にも呼ぶ
  let all = [], owned = [];
  const swapOut = new Set();   // 入れ替えで売るカード(ラインナップに入れず、出品する)
  async function loadOwned() {
    all = await myCards(api.gql, t.rarity, sportOf(t));
    const bySlug = new Map();
    for (const c of all) if (c.seasonYear === t.seasonYear && c.player && !bySlug.has(c.player)) bySlug.set(c.player, c);
    const ps = (await pool([...bySlug.keys()], 3, getPlayer)).filter((p) => p && p.league === t.competition);
    owned = ps.map((p) => { const c = bySlug.get(p.id); return proj({ ...p, card: c.slug, cost: c.cost, since: c.since, floor: p.price, price: null }); });
    return optimize(owned.filter((c) => !swapOut.has(c.card)));
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
      lines.push(nba ? "手持ちでは 5 枚そろわない(星の合計の上限内で 5 枚必要)。代わりに購入候補を出します" : "手持ちでは 5 枚そろわない(GK・DF・MF・FW が各 1 枚以上必要)。代わりに購入候補を出します");
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

  // 学習: 入賞ラインの目安と、今の予想で届きそうか。記録が 2 節以上あって 8 割に届かない大会は、購入を見送る(残高を届く大会に回す)
  const line = cutoffLine(shared.learn.cutoffs[t.name]);
  const ptsNow = best?.pts ?? plans[0]?.pts ?? 0;
  const rr = reach(ptsNow, line, cfg.learn?.minCutoffs ?? 2);
  if (line) lines.push("", `**入賞ライン(学習)**: 賞金 ${line.rank} 位まで・目安 ${line.score.toFixed(0)} 点(過去 ${line.n} 節) / 予想 ${ptsNow.toFixed(0)} 点${rr != null ? `(${Math.round(rr * 100)}%)` : ""}`);
  const farOff = rr != null && rr < (cfg.learn?.skipBelowReach ?? 0.8);
  // 予想を記録しておき、節が終わったら実際の点数と比べる(サッカーの予想の補正に使う)
  if (!nba) {
    const pool = [...owned, ...(mktCache || [])].filter((c) => c.proj > 0).sort((a, b) => b.proj - a.proj).slice(0, 60);
    const pend = (shared.learn.pending[fixture.slug] ||= { sport: "FOOTBALL", players: {} });
    for (const c of pool) pend.players[c.id] = [c.pos, +(c.proj / calibration(shared.learn.samples, c.pos)).toFixed(2)];
  }

  // 自動購入: buyPlan のプランを、1 枚と週の上限の範囲で買う。手持ちにある選手は買わない
  // プランは残高に合わせて選ぶ(buyPlan: cheap / plus / auto)。足りなければこの節は見送り、締切前に何度も通知しないよう済みにする
  const have0 = new Set(owned.map((c) => c.id));
  const pick = api.authed && trading ? pickPlan(plans, t.buyPlan ?? tr.buyPlan, shared.balance, tr.reserveUsd || 0, have0) : { plan: plans.find((p) => p.title.startsWith((t.buyPlan ?? tr.buyPlan) === "plus" ? "プラスアルファ" : "最安")) || plans[0] };
  const plan = pick.plan;
  if (plans.length && api.authed && farOff && t.autoBuy !== false) {
    lines.push("", `**自動購入**: 見送り(入賞ラインの ${Math.round(rr * 100)}% しか届かない見込み)。残高は届きそうな大会に回します`);
    t.skipped = true;
  } else if (plans.length && api.authed && !plan && t.autoBuy !== false) {
    lines.push("", `**自動購入**: 見送り(${pick.why})。賞金やカードの売却で残高が増えたら、自動で始めます`);
    t.skipped = true;
  } else if (plan && api.authed && t.autoBuy === false) {
    lines.push("", "(この大会は自動購入しない設定: autoBuy=false。購入はリンクから)");
  } else if (plan && api.authed) {
    const have = new Set(owned.map((c) => c.id));
    const buys = planBuys(plan.lineup.filter((c) => !have.has(c.id)), tr, shared.spent ?? spentInWeek(all));
    lines.push("", `**自動購入**(${plan.title}・1枚 $${tr.perCardMaxUsd}・週 $${tr.weeklyMaxUsd} まで${shared.balance != null ? `・残高 $${shared.balance.toFixed(2)}` : ""})${tradeNote}`);
    let bought = 0;
    for (const b of buys) {
      if (!b.ok) { lines.push(`- 見送り ${b.name} $${b.price?.toFixed(2)}: ${b.why}`); continue; }
      if (!trading) { lines.push(`- 購入予定 ${b.name} $${b.price.toFixed(2)}`); continue; }
      try { const paid = await trader.buy(b.card, b.price); bought++; shared.spent += paid; if (shared.balance != null) shared.balance -= paid; lines.push(`- ✅ 購入 ${b.name} $${paid.toFixed(2)}`); }
      catch (e) { lines.push(`- ⚠️ 購入できず ${b.name}: ${e.message}`); }
    }
    if (bought) {
      best = await loadOwned();
      lines.push(best ? "手持ちで 5 枚そろったので、このまま組みます" : "まだ 5 枚そろわない(次の実行で続きを買います)");
    }
    if (trading && !best && buys.some((b) => b.ok)) lines.push("(締切前の次の実行で、もう一度買います)");
  } else if (plans.length) {
    lines.push("(買った後の次の実行で、手持ちから組んで登録します)");
  }

  // 入れ替え(config の swap): 値上がりしたカードを、似た働きの安い選手に替える。先に代わりを買い、そろってから値上がりしたカードを出品する
  // (出品してもすぐ売れるとは限らないので、先に買って今節のラインナップを欠かさない)
  const sw = cfg.swap;
  if (api.authed && best && sw?.enabled && t.autoBuy !== false) {
    const opts = { ...sw, minHoldDays: tr.minHoldDays };
    const gainers = owned.filter((c) => c.cost && c.floor != null && (c.floor / c.cost - 1) * 100 >= sw.gainPct);
    const swaps = gainers.length ? swapCandidates(owned, await marketCands(), opts) : [];
    if (swaps.length) {
      lines.push("", `**入れ替え**(買値から +${sw.gainPct}% 以上値上がりしたカードを、予想 ${Math.round(sw.minProjRatio * 100)}% 以上・価格 ${Math.round(sw.maxPriceRatio * 100)}% 以下の選手に替える)${tradeNote}`);
      for (const x of swaps) {
        const head = `- ${x.sell.name}(${POS_JA[x.sell.pos] || x.sell.pos}): 買値 $${x.sell.cost.toFixed(2)} → 今 $${x.sell.floor.toFixed(2)}(+${Math.round(x.gain)}%)\n  代わり: ${x.sub.name}(${x.sub.club}・予想 ${x.sub.proj.toFixed(0)} / ${x.sell.name} は ${x.sell.proj.toFixed(0)})$${x.sub.price.toFixed(2)} / 入れ替えると手元に約 +$${x.profit.toFixed(2)}\n  <${cardUrl(x.sub.card, t)}>`;
        const [b] = planBuys([x.sub], tr, shared.spent ?? spentInWeek(all));
        if (!b.ok) { lines.push(`${head}\n  見送り: ${b.why}`); continue; }
        if (shared.balance != null && x.sub.price + (tr.reserveUsd || 0) > shared.balance) { lines.push(`${head}\n  見送り: 残高 $${shared.balance.toFixed(2)} では足りない`); continue; }
        if (!trading) { lines.push(`${head}\n  (入れ替え予定)`); continue; }
        try { const paid = await trader.buy(x.sub.card, x.sub.price); shared.spent += paid; if (shared.balance != null) shared.balance -= paid; swapOut.add(x.sell.card); lines.push(`${head}\n  ✅ 代わりを購入 $${paid.toFixed(2)}(${x.sell.name} は下の売却で出品)`); }
        catch (e) { lines.push(`${head}\n  ⚠️ 代わりを買えず(入れ替えはしない): ${e.message}`); }
      }
      if (swapOut.size) best = await loadOwned() || best;
    }
  }

  // 手持ちで 5 枚そろわない間は済みにしない。アプリで買った後も、締切前の次の実行で組んで登録する
  if (api.authed && !best && !t.skipped) t.retry = true;
  if (!best && !plans.length) lines.push("5 枚そろう組み合わせが無い");
  if (best) {
    lines.push("", "**ラインナップ**", ...lineupLines(best, false), `予想合計 ${best.pts.toFixed(0)}(ボーナス抜き)`);
    if (env.SORARE_SUBMIT === "true") {
      const cap = best.lineup.find((c) => c.id === best.captain)?.card ?? null;   // NBA はキャプテン無し
      const id = await submitLineup(api.gql, leaderboard.id, best.lineup, cap);
      lines.push(`✅ ラインナップを登録しました(${id})`);
    } else {
      lines.push("(提案のみ。登録するには SORARE_SUBMIT=true)");
    }
  }

  // 売却候補: 条件に当てはまるカードを、ラインナップ・保有期間・買値を確かめてから出品する
  if (owned.length) {
    const sell = sellCandidates(owned, cfg.sell).map((c) => ({ ...c, ask: sellPrice(c.floor, cfg.sell.undercutPct) }));
    // 学習: 手持ちカードの値動きを記録し、値上がりの後に下がり始めたら売る(最高値から dropPct% 下がり、まだ買値から +minGainPct% 以上ある時)
    const now = Date.now();
    for (const c of owned) {
      if (c.floor == null) continue;
      shared.learn.prices[c.card] = addPrice(shared.learn.prices[c.card], now, c.floor);
      const sig = sellSignal(shared.learn.prices[c.card], c.cost, cfg.learn?.sellTiming);
      if (!sig) continue;
      const s = sell.find((x) => x.card === c.card);
      if (s) s.reasons.push(sig); else sell.push({ ...c, reasons: [sig], ask: sellPrice(c.floor, cfg.sell.undercutPct) });
    }
    for (const c of owned.filter((c) => swapOut.has(c.card))) {
      const s = sell.find((x) => x.card === c.card);
      if (s) s.reasons.push("入れ替え");
      else sell.push({ ...c, reasons: ["入れ替え"], ask: sellPrice(c.floor, cfg.sell.undercutPct) });
    }
    if (sell.length) {
      lines.push("", `**売却候補**(条件: ${cfg.sell.maxAge + 1}歳以上、スタメン率 ${Math.round(cfg.sell.minStartRate * 100)}% 未満、または買値から +${cfg.sell.gainPct}% 以上の値上がり)${tradeNote}`);
      const inLineup = new Set(best ? best.lineup.map((c) => c.card) : []);
      for (const c of planSells(sell, tr, inLineup)) {
        const head = `- ${c.name}(${c.club}・${POS_JA[c.pos]}): ${c.reasons.join("・")} / 今の最安出品 ${c.floor != null ? "$" + c.floor.toFixed(2) : "なし"}`;
        if (!c.ok) { lines.push(`${head} / 見送り: ${c.why}\n  <${cardUrl(c.card, t)}>`); continue; }
        if (!trading) { lines.push(`${head} / 出品予定 $${c.price.toFixed(2)}\n  <${cardUrl(c.card, t)}>`); continue; }
        try { const listed = await trader.list(c.card, c.price); lines.push(`${head} / ✅ 出品 $${listed.toFixed(2)}\n  <${cardUrl(c.card, t)}>`); }
        catch (e) { lines.push(`${head} / ⚠️ 出品できず: ${e.message}\n  <${cardUrl(c.card, t)}>`); }
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
