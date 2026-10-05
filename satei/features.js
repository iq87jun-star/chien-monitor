// 出品タイトル・説明文(または査定画面の入力)から、キャラごとの所持・凸数・モチーフ武器(餅)を読み取り、
// 値付けモデルの特徴量にする。
import { CHARS, norm } from "./chars.js";

const KANJI_NUM = { 無: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6 };

// 名前の後ろ(次の区切りまで)を見て、凸数と餅を読む
function readAfter(tail) {
  const seg = tail.slice(0, 10).split(/[、,，/／|｜\n。()()【】\[\]]/)[0];
  let cons = null;
  let mochi = /餅|モチ|ﾓﾁ/.test(seg);
  if (/両完凸/.test(seg)) {
    cons = 6;
    mochi = true;
  } else if (/完凸/.test(seg)) cons = 6;
  else {
    const m = /(?:^|[^0-9])([0-6])凸|[CE]([0-6])(?![0-9])|([無一二三四五六])凸/.exec(seg);
    if (m) cons = m[1] != null ? Number(m[1]) : m[2] != null ? Number(m[2]) : KANJI_NUM[m[3]];
  }
  return { cons, mochi };
}

// テキスト → { キャラ名: { cons: 0〜6, mochi: bool } }
export function parseRoster(text, game) {
  const t = norm(text ?? "");
  const out = {};
  const names = Object.entries(CHARS[game]).flatMap(([name, alias]) => [name, ...alias].map((a) => [norm(a), name]));
  // 長い名前から当てる(「丹恒騰荒」を「丹恒」より先に)
  names.sort((a, b) => b[0].length - a[0].length);
  const taken = new Array(t.length).fill(false);
  const hits = [];
  for (const [alias, name] of names) {
    for (let i = t.indexOf(alias); i >= 0; i = t.indexOf(alias, i + 1)) {
      if (taken.slice(i, i + alias.length).some(Boolean)) continue;
      for (let k = i; k < i + alias.length; k++) taken[k] = true;
      hits.push({ i, end: i + alias.length, name });
    }
  }
  // 名前の後ろは、次のキャラ名の手前までを見る
  hits.sort((a, b) => a.i - b.i);
  hits.forEach((h, n) => {
    const { cons, mochi } = readAfter(t.slice(h.end, hits[n + 1]?.i ?? t.length));
    const prev = out[h.name] ?? { cons: 0, mochi: false };
    out[h.name] = { cons: Math.max(prev.cons, cons ?? 0), mochi: prev.mochi || mochi };
  });
  return out;
}

// 一覧の「星5キャラクターの数：30体」などを数値に
export function infoNumber(info, re) {
  for (const s of info ?? []) {
    const m = re.exec(s);
    if (m) return Number(m[1]);
  }
  return null;
}

export const STAR5_RE = /星5キャラ(?:クター)?の数：(\d+)/;

// 特徴量の並び(モデルの重みと同じ順)
export function featureNames(game) {
  const f = ["bias", "star5_log", "star5_missing", "starter"];
  for (const name of Object.keys(CHARS[game])) f.push(`has:${name}`, `cons:${name}`, `mochi:${name}`);
  return f;
}

// roster と星5の数から特徴量のベクトルを作る
export function featurize(game, { roster, star5, starter = false }) {
  const names = featureNames(game);
  const x = new Array(names.length).fill(0);
  const idx = Object.fromEntries(names.map((n, i) => [n, i]));
  x[idx.bias] = 1;
  if (star5 && star5 > 0 && star5 <= 80) x[idx.star5_log] = Math.log1p(star5);
  else x[idx.star5_missing] = 1;
  x[idx.starter] = starter ? 1 : 0;
  for (const [name, { cons, mochi }] of Object.entries(roster)) {
    if (idx[`has:${name}`] == null) continue;
    x[idx[`has:${name}`]] = 1;
    x[idx[`cons:${name}`]] = cons / 6;
    x[idx[`mochi:${name}`]] = mochi ? 1 : 0;
  }
  return x;
}
