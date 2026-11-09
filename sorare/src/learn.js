// 結果からの学習(記録は state/learn.json。GitHub Actions のキャッシュで実行をまたいで残す)。
// ここは記録を読んで値を出す純粋な関数だけ(test/learn.test.js)。記録を集めるのは run.js と data.js。
//   cutoffs: 大会名 → [{ fixture, rank, score, teams }]  賞金(現金)が出た最後の順位とその点数
//   pending: 節の slug → { sport, players: { 選手 slug: [ポジション, 予想] } }  結果が出たら samples に移す
//   samples: [{ pos, proj, actual }]  予想と実際の点数(サッカー)
//   prices:  カード slug → [[時刻, 最安出品(USD)]]  手持ちカードの値動き

export function emptyLearn() { return { cutoffs: {}, pending: {}, samples: [], prices: {} }; }

export function median(a) {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

// ポジションごとの予想の補正: 実際 ÷ 予想 の中央値。件数が少ないうちは 1 に寄せる(10 件で半分)。0.7〜1.3 に収める
export function calibration(samples, pos) {
  const r = (samples || []).filter((s) => s.pos === pos && s.proj > 5).map((s) => s.actual / s.proj);
  if (!r.length) return 1;
  return clamp((r.length * median(r) + 10) / (r.length + 10), 0.7, 1.3);
}

// 入賞ライン(賞金が出た最後の順位の点数)の目安: 直近 5 節の中央値
export function cutoffLine(list) {
  const l = (list || []).slice(-5);
  return l.length ? { score: median(l.map((x) => x.score)), rank: l.at(-1).rank, n: l.length } : null;
}

// 届く見込み = 予想(ボーナス抜き) ÷ 入賞ライン(ボーナス込み)。記録が minN 節に満たなければ null(判断しない)
export function reach(pts, line, minN = 2) {
  return line && line.n >= minN && line.score > 0 ? pts / line.score : null;
}

// 売り時: 買ってからの最高値が買値の +(minGainPct + dropPct)% 以上になり、そこから dropPct% 以上下がり始めた時。
// ただし今も買値から +minGainPct% 以上ある時だけ(値上がり分を残して売る)
export function sellSignal(series, cost, { dropPct = 10, minGainPct = 10 } = {}) {
  if (!cost || !series?.length) return null;
  const peak = Math.max(...series.map((p) => p[1])), last = series.at(-1)[1];
  if (peak >= cost * (1 + (minGainPct + dropPct) / 100) && last <= peak * (1 - dropPct / 100) && last >= cost * (1 + minGainPct / 100)) {
    return `最高値 $${peak.toFixed(2)} から ${Math.round((1 - last / peak) * 100)}% 下がり始めた`;
  }
  return null;
}

// 値動きの記録に 1 点足す(2 時間以内の重複は上書き、最大 60 点)
export function addPrice(series, t, price) {
  const s = [...(series || [])];
  if (s.length && t - s.at(-1)[0] < 2 * 3600e3) s[s.length - 1] = [t, price]; else s.push([t, price]);
  return s.slice(-60);
}

// 賞金(現金)が出る最後の順位。rewardsConfig.ranking の usdAmount か ethAmount がある段のうち一番下
export function cashRank(ranking) {
  const paid = (ranking || []).filter((r) => r.usdAmount || r.ethAmount).map((r) => r.toRank);
  return paid.length ? Math.max(...paid) : null;
}
