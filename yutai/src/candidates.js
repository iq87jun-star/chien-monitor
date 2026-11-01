// candidates.csv(自分で書く候補一覧)の読み取り
import { parseCsv } from './jsf.js';

export function parseCandidates(text) {
  const [head, ...rows] = parseCsv(text);
  const idx = (k) => head.indexOf(k);
  const n = (v) => (v === '' || v == null ? null : Number(v));
  return rows.filter((r) => r[idx('コード')]).map((r) => ({
    code: r[idx('コード')].trim(),
    name: r[idx('銘柄名')] ?? '',
    recordDate: r[idx('権利確定日')].trim(),
    shares: n(r[idx('必要株数')]),
    value: n(r[idx('優待価値円')]),
    dividend: n(r[idx('1株配当円')]) ?? 0,
    ippanStock: (r[idx('一般在庫')] || '不明').trim(),
    ippanEntry: (r[idx('一般で入る日')] || '').trim() || null,
    price: n(r[idx('株価')]),
    memo: r[idx('メモ')] ?? '',
  }));
}
