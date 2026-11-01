// 優待クロス 1 件の損益見積もりと判定。
// クロス = 現物買い + 同数の信用売り → 権利付最終日の翌営業日に現渡しで相殺。
// 値動きの損益は打ち消し合うので、残るのは「優待価値 − 費用」。
import { holdDays, kashiDays, lastCumDate } from './calendar.js';
import { estimateMaxRate } from './jsf.js';

const yen = (v) => Math.round(v);

// c: 候補 1 行 / ctx: { cfg, shina(コード→最新行), prices(コード→株価) }
export function evaluate(c, { cfg, shina = new Map(), prices = new Map() }) {
  const cum = lastCumDate(c.recordDate);
  const kd = kashiDays(cum);
  const row = shina.get(c.code);
  const price = c.price ?? row?.price ?? prices.get(c.code) ?? null;
  const notes = [];
  if (price == null) {
    return { ...c, cum, kashiDays: kd, price: null, verdict: '株価不明', notes: ['candidates.csv の 株価 を埋める'] };
  }
  const notional = price * c.shares;
  const base = c.value - (c.dividend ?? 0) * c.shares * cfg.dividendTaxRate - cfg.commissionYenPerLeg * 2;

  // 制度信用: 権利付最終日に入る(日数を最小にする)
  let maxRate = row?.maxRate ?? null;
  const maxRateSource = maxRate != null ? '日証金' : '推定';
  if (maxRate == null) maxRate = estimateMaxRate(price);
  const seidoFee = notional * cfg.seidoLendingRate * kd / 365;
  const gyakuWorst = maxRate * kd * c.shares;
  const gyakuStress = gyakuWorst * cfg.maxRateStress;
  const seidoNetWorst = base - seidoFee - gyakuWorst;
  const seidoNetStress = base - seidoFee - gyakuStress;
  const seidoNetNoGyaku = base - seidoFee;
  const restrict = row?.restrict ?? '';
  const seidoBlocked = restrict.includes('停止');
  if (seidoBlocked) notes.push('日証金が新規売りを停止中(制度信用では入れない)');
  else if (restrict.includes('注意')) notes.push('日証金の注意喚起中(逆日歩が高くなりやすい)');
  if (kd >= 3) notes.push(`品貸日数 ${kd} 日(連休をまたぐので逆日歩の最悪額が大きい)`);
  if (row?.excess > 0) notes.push(`貸株超過 ${row.excess.toLocaleString()} 株(すでに逆日歩が付きうる)`);

  // 一般信用: 逆日歩なし。在庫があれば早めに入ることも多い
  const ippanEntry = c.ippanEntry || cum;
  const hd = holdDays(ippanEntry, cum);
  const ippanFee = notional * cfg.ippanLendingRate * hd / 365;
  const ippanNet = base - ippanFee;

  let verdict;
  if (c.ippanStock !== 'なし' && ippanNet >= cfg.minProfitYen) {
    verdict = c.ippanStock === 'あり' ? '一般信用で入る' : '一般信用で入る(在庫を確認)';
  } else if (!seidoBlocked && seidoNetStress >= cfg.minProfitYen) {
    verdict = '制度信用で入る(逆日歩が最悪でもプラス)';
  } else if (!seidoBlocked && seidoNetWorst >= cfg.minProfitYen) {
    verdict = '見送り寄り(最高料率の引き上げがあると赤字)';
  } else {
    verdict = '見送り';
  }

  return {
    ...c, cum, kashiDays: kd, price, notional: yen(notional), maxRate, maxRateSource, restrict,
    seidoFee: yen(seidoFee), gyakuWorst: yen(gyakuWorst), gyakuStress: yen(gyakuStress),
    seidoNetNoGyaku: yen(seidoNetNoGyaku), seidoNetWorst: yen(seidoNetWorst), seidoNetStress: yen(seidoNetStress),
    ippanEntry, holdDays: hd, ippanFee: yen(ippanFee), ippanNet: yen(ippanNet), verdict, notes,
  };
}

// 権利付最終日の日証金データ(申込日 = 権利付最終日)から実際の逆日歩を出す
export function scorePaper(ev, cumRow) {
  if (!cumRow) return null;
  const gyaku = (cumRow.rate ?? 0) * ev.shares; // 当日品貸料率は品貸日数分の金額
  return {
    code: ev.code, name: ev.name, cum: ev.cum, shares: ev.shares,
    gyakuActual: yen(gyaku), gyakuWorst: ev.gyakuWorst, gyakuStress: ev.gyakuStress,
    withinWorst: gyaku <= ev.gyakuWorst + 0.5, withinStress: gyaku <= ev.gyakuStress + 0.5,
    seidoNetActual: yen(ev.seidoNetNoGyaku - gyaku), verdict: ev.verdict,
  };
}
