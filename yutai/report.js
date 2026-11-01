// candidates.csv の候補を日証金データで判定し、report.md を書く。
// 権利付最終日を過ぎた候補は、その日の実際の逆日歩で採点する(紙上フォワード)。
// YUTAI_DISCORD_WEBHOOK があれば、近い権利付最終日と新しい採点を Discord に送る。
//   node report.js            … 今日(JST)基準
//   YUTAI_TODAY=2026-11-26 node report.js … 基準日を指定(試す時用)
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { addBizDays, addDays, isBizDay, todayJst } from './src/calendar.js';
import { evaluate, scorePaper } from './src/cost.js';
import { parseCandidates } from './src/candidates.js';
import { fromSlimCsv, parseCsv } from './src/jsf.js';

const here = (p) => new URL(p, import.meta.url);
const cfg = JSON.parse(await readFile(here('./config.json'), 'utf8'));
const today = process.env.YUTAI_TODAY || todayJst();

// data/jsf の全スナップショット(申込日 → コード → 行)
async function loadSnapshots() {
  const dir = here('./data/jsf/');
  let files = [];
  try { files = (await readdir(dir)).filter((f) => /^shina-\d{4}-\d{2}-\d{2}\.csv$/.test(f)).sort(); } catch {}
  const snaps = new Map();
  for (const f of files) {
    const rows = fromSlimCsv(await readFile(new URL(f, dir), 'utf8'));
    snaps.set(f.slice(6, 16), new Map(rows.map((r) => [r.code, r])));
  }
  return snaps;
}

async function loadPrices() {
  try {
    const [, ...rows] = parseCsv(await readFile(here('./data/prices-latest.csv'), 'utf8'));
    return new Map(rows.map(([c, p]) => [c, Number(p)]));
  } catch { return new Map(); }
}

const fmt = (v) => (v == null ? '-' : Math.round(v).toLocaleString());
// ETF・REIT は優待がほぼ無いので混雑銘柄から外す(コード帯と名前で判定)
const isEtf = (code, name = '') => /^1[3-6]\d\d$/.test(code) || /ＥＴＦ|ダウ|日経|ＴＯＰＩＸ|ベア|ブル|インバース|レバ|リート|投資法人|ＲＥＩＴ/.test(name);

const candidates = parseCandidates(await readFile(here('./candidates.csv'), 'utf8'))
  .filter((c) => !c.code.startsWith('9999') || process.env.YUTAI_KEEP_SAMPLE);
const snaps = await loadSnapshots();
const prices = await loadPrices();
const latestDate = [...snaps.keys()].at(-1) ?? null;
const latest = latestDate ? snaps.get(latestDate) : new Map();

const evals = [];
const errors = [];
for (const c of candidates) {
  try {
    if (!c.shares || c.value == null) throw new Error('必要株数・優待価値円が空');
    evals.push(evaluate(c, { cfg, shina: latest, prices }));
  } catch (e) { errors.push(`${c.code} ${c.name}: ${e.message}`); }
}
const upcoming = evals.filter((e) => e.cum >= today).sort((a, b) => a.cum.localeCompare(b.cum));
const past = evals.filter((e) => e.cum < today).sort((a, b) => a.cum.localeCompare(b.cum));

// 紙上フォワード: 権利付最終日のスナップショットで採点(当時の最高料率で判定し直す)
const scored = [];
const pending = [];
for (const e of past) {
  const snapAtCum = snaps.get(e.cum);
  const before = [...snaps.keys()].filter((d) => d < e.cum).at(-1);
  if (!snapAtCum) { pending.push(e); continue; }
  const evAtEntry = evaluate(e, { cfg, shina: before ? snaps.get(before) : new Map(), prices });
  scored.push(scorePaper(evAtEntry, snapAtCum.get(e.code) ?? { rate: 0 }));
}

// 混雑銘柄: 近く決算(権利)を迎え、すでに貸株超過の銘柄 = 制度クロスが集まっている所
const horizon = addDays(today, cfg.crowdingWindowDays);
const crowded = [...latest.values()]
  .filter((r) => r.event === '決算' && r.excess > 0 && r.eventDate >= today && r.eventDate <= horizon && !isEtf(r.code, r.name))
  .sort((a, b) => b.excess * (b.price ?? 0) - a.excess * (a.price ?? 0))
  .slice(0, cfg.crowdingTop);

const md = [];
md.push(`# 優待クロス 判定レポート(${today})`, '');
md.push(`日証金データ: 申込日 ${latestDate ?? 'なし(node fetch.js を先に実行)'} / 前提: 制度貸株料 ${(cfg.seidoLendingRate * 100).toFixed(2)}%・一般貸株料 ${(cfg.ippanLendingRate * 100).toFixed(2)}%・最高料率の引き上げ想定 ×${cfg.maxRateStress}・最低利益 ${fmt(cfg.minProfitYen)} 円`, '');
md.push('## これからの候補', '');
if (!upcoming.length) md.push('(なし。candidates.csv に候補を書く)', '');
else {
  md.push('| 権利付最終日 | コード | 銘柄 | 株数 | 優待 | 品貸日数 | 最高料率 | 制度(逆日歩なし) | 制度(最悪) | 制度(引き上げ) | 一般 | 判定 |');
  md.push('|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|');
  for (const e of upcoming) {
    if (e.price == null) { md.push(`| ${e.cum} | ${e.code} | ${e.name} | ${e.shares} | ${fmt(e.value)} | ${e.kashiDays} | - | - | - | - | - | ${e.verdict} |`); continue; }
    md.push(`| ${e.cum} | ${e.code} | ${e.name} | ${e.shares} | ${fmt(e.value)} | ${e.kashiDays} | ${e.maxRate.toFixed(2)}(${e.maxRateSource}) | ${fmt(e.seidoNetNoGyaku)} | ${fmt(e.seidoNetWorst)} | ${fmt(e.seidoNetStress)} | ${fmt(e.ippanNet)}(${e.holdDays}日) | ${e.verdict} |`);
  }
  md.push('');
  for (const e of upcoming.filter((x) => x.notes?.length)) md.push(`- ${e.code} ${e.name}: ${e.notes.join(' / ')}`);
  md.push('');
}

md.push('## 紙上フォワード(権利付最終日を過ぎた候補)', '');
if (!scored.length && !pending.length) md.push('(まだなし)', '');
if (scored.length) {
  md.push('| 権利付最終日 | コード | 銘柄 | 当時の判定 | 逆日歩 実際 | 最悪の想定 | 引き上げ想定 | 制度で入った場合の損益 |');
  md.push('|---|---|---|---|---:|---:|---:|---:|');
  for (const s of scored) {
    md.push(`| ${s.cum} | ${s.code} | ${s.name} | ${s.verdict} | ${fmt(s.gyakuActual)} | ${fmt(s.gyakuWorst)}${s.withinWorst ? '' : ' ⚠'} | ${fmt(s.gyakuStress)}${s.withinStress ? '' : ' ⚠'} | ${fmt(s.seidoNetActual)} |`);
  }
  const n = scored.length;
  const inS = scored.filter((s) => s.withinStress).length;
  const go = scored.filter((s) => s.verdict.startsWith('制度'));
  md.push('', `集計: ${n} 件 / 逆日歩が引き上げ想定以内 ${inS} 件(${((inS / n) * 100).toFixed(0)}%) / 「制度で入る」判定 ${go.length} 件の損益合計 ${fmt(go.reduce((a, s) => a + s.seidoNetActual, 0))} 円・赤字 ${go.filter((s) => s.seidoNetActual < 0).length} 件`, '');
}
if (pending.length) md.push(`採点待ち(権利付最終日のデータがまだ無い): ${pending.map((e) => `${e.code}(${e.cum})`).join(', ')}`, '');

md.push(`## 混雑銘柄(${cfg.crowdingWindowDays} 日以内に権利・すでに貸株超過)`, '');
md.push('制度信用のクロスが集まっている銘柄。優待の中身はここに無いので、気になるものは自分で調べて candidates.csv に足す。', '');
if (!crowded.length) md.push('(なし)', '');
else {
  md.push('| 権利 | コード | 銘柄 | 貸借値段 | 貸株超過 | 最高料率 | 品貸料率(直近) | 制限 |', '|---|---|---|---:|---:|---:|---:|---|');
  for (const r of crowded) md.push(`| ${r.eventDate} | ${r.code} | ${r.name} | ${fmt(r.price)} | ${fmt(r.excess)} | ${r.maxRate ?? '-'} | ${r.rate ?? 0} | ${r.restrict} |`);
  md.push('');
}
if (errors.length) md.push('## 読めなかった候補', '', ...errors.map((x) => `- ${x}`), '');

await writeFile(here('./report.md'), md.join('\n'));
console.log(md.join('\n'));

// Discord: 権利付最終日が近い候補と、前営業日の採点
const hook = process.env.YUTAI_DISCORD_WEBHOOK;
if (hook && isBizDay(today)) {
  const soon = addBizDays(today, cfg.remindBizDays);
  const near = upcoming.filter((e) => e.cum <= soon);
  const prev = addBizDays(today, -1);
  const fresh = scored.filter((s) => s.cum === prev);
  const lines = [];
  for (const e of near) lines.push(`${e.cum === today ? '【今日】' : ''}${e.cum} ${e.code} ${e.name}: ${e.verdict}(制度 引き上げ想定 ${fmt(e.seidoNetStress)} 円 / 一般 ${fmt(e.ippanNet)} 円)`);
  for (const s of fresh) lines.push(`採点 ${s.code} ${s.name}: 逆日歩 ${fmt(s.gyakuActual)} 円(最悪 ${fmt(s.gyakuWorst)} 円)→ 制度なら ${fmt(s.seidoNetActual)} 円`);
  if (lines.length) {
    const res = await fetch(hook, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ content: `優待クロス\n${lines.join('\n')}`.slice(0, 1900) }) });
    if (!res.ok) console.error(`Discord への送信に失敗: HTTP ${res.status}`);
  }
}
