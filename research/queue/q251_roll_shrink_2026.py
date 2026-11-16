# -*- coding: utf-8 -*-
"""docs/244 Q251(診断・セル 0・2026-11-16 登録): 水曜のロール(円クロス 5 本の売り・水曜 20 UTC → 木曜 00 UTC・金利差の門 2.0pp)が 2026 年に小さくなった理由。
通貨 × 年で、政策金利差・スワップ 3 日分の理論値(金利差 × 3 / 360)・実際の下げ幅(コスト前)・コスト・コスト後を並べ、下げ幅を金利差で説明できるかを見る。
使い方: cd research && python3 -W ignore queue/q251_roll_shrink_2026.py   出力: results/q251_roll_shrink_pair_year.csv・_summary.csv"""
import sys, os
from q_common import *
from scipy import stats as sps
from q20_wed_swap_carry import rate_series, RATES
from q205_roll5_sma200_state import PAIRS, GATE, bars
def pair_frame(s):
    o = bars(s)["open"]; h = bars(s); t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; p0 = o.reindex(t).values; p1 = o.reindex(t + pd.Timedelta(hours=4)).values; ok = ~np.isnan(p0) & ~np.isnan(p1); t = t[ok]; p0 = p0[ok]; p1 = p1[ok]; d = t.normalize()
    hi = h["high"]; lo = h["low"]; rng = np.array([(hi[x:x + pd.Timedelta(hours=3)].max() / lo[x:x + pd.Timedelta(hours=3)].min() - 1) for x in t])
    diff = (rate_series(s[:3], d) - rate_series("JPY", d)).values
    return pd.DataFrame({"sym": s, "diff": diff, "gross": -(p1 / p0 - 1), "cost": cost(s, p0), "range": rng}, index=d)
if __name__ == "__main__":
    P = pd.concat([pair_frame(s) for s in PAIRS]).sort_index(kind="stable"); P["net"] = P.gross - P.cost; P["theory"] = P["diff"] * 3 / 360 / 100; P["open"] = P["diff"] >= GATE; P["per"] = [str(d.year) if d.year < 2026 else ("2026 前半" if d.month <= 6 else "2026 後半") for d in P.index]
    rows = []
    def agg(x, **k):
        g = x[x.open]; c = x[~x.open]
        return dict(**k, weeks=len(x), open_n=len(g), diff_pp=round(float(g["diff"].mean()), 2) if len(g) else None, theory_bps=round(float(g.theory.mean()) * 1e4, 2) if len(g) else None, gross_bps=round(float(g.gross.mean()) * 1e4, 2) if len(g) else None, cost_bps=round(float(g.cost.mean()) * 1e4, 2) if len(g) else None, net_bps=round(float(g.net.mean()) * 1e4, 2) if len(g) else None,
                    net_t=round(float(g.net.mean() / g.net.std() * np.sqrt(len(g))), 2) if len(g) > 2 and g.net.std() > 0 else None, net_sd_bps=round(float(g.net.std()) * 1e4, 1) if len(g) > 1 else None, win=round(float((g.net > 0).mean()) * 100, 0) if len(g) else None, range_bps=round(float(g["range"].mean()) * 1e4, 1) if len(g) else None,
                    closed_n=len(c), closed_diff_pp=round(float(c["diff"].mean()), 2) if len(c) else None, closed_net_bps=round(float(c.net.mean()) * 1e4, 2) if len(c) else None)
    for per in sorted(P.per.unique()):
        if per < "2022": continue
        rows.append(agg(P[P.per == per], sym="5 本まとめ", period=per))
    for s in PAIRS:
        for per in ("2023", "2024", "2025", "2026 前半", "2026 後半"): rows.append(agg(P[(P.sym == s) & (P.per == per)], sym=s, period=per))
    D = pd.DataFrame(rows); D.to_csv("results/q251_roll_shrink_pair_year.csv", index=False)
    summ = []; G = P[P.open & (P.index >= "2022-01-01")]
    sl = sps.linregress(G["diff"].values, G.gross.values * 1e4); summ.append(dict(item="門が開いた通貨 × 週(2022〜): 下げ幅(bps)= a + b × 金利差(pp)", value=f"a = {sl.intercept:.2f}, b = {sl.slope:.2f}(標準誤差 {sl.stderr:.2f}・理論値 0.83), n = {len(G)}"))
    A = P[P.index >= "2022-01-01"]; sl2 = sps.linregress(A["diff"].values, A.gross.values * 1e4); summ.append(dict(item="全通貨 × 週(2022〜・門を問わない)", value=f"a = {sl2.intercept:.2f}, b = {sl2.slope:.2f}(標準誤差 {sl2.stderr:.2f}), n = {len(A)}"))
    for lo, hi in ((-9, 1), (1, 2), (2, 3), (3, 4), (4, 9)):
        x = A[(A["diff"] >= lo) & (A["diff"] < hi)]; summ.append(dict(item=f"金利差 {lo if lo > -9 else '〜'}{'〜' if lo > -9 else ''}{hi if hi < 9 else ''}pp{'以上' if hi == 9 else ''}(2022〜)", value=f"n = {len(x)}, 理論値 {x.theory.mean() * 1e4:.2f}, 下げ幅 {x.gross.mean() * 1e4:.2f}, コスト {x.cost.mean() * 1e4:.2f}, コスト後 {x.net.mean() * 1e4:.2f} bps(t {x.net.mean() / x.net.std() * np.sqrt(len(x)):.2f})"))
    a = P[P.open & (P.index.year >= 2023) & (P.index.year <= 2025)]; b = P[P.open & (P.index.year == 2026)]; wa = a.net.groupby(level=0).mean(); wb = b.net.groupby(level=0).mean(); tt = sps.ttest_ind(wa, wb, equal_var=False)
    summ.append(dict(item="2023〜25 年 対 2026 年(門が開いた通貨の週平均・コスト後)", value=f"{wa.mean() * 1e4:.2f} bps({len(wa)} 週・ばらつき {wa.std() * 1e4:.1f})対 {wb.mean() * 1e4:.2f} bps({len(wb)} 週・ばらつき {wb.std() * 1e4:.1f})、差の t = {tt.statistic:.2f}, p = {tt.pvalue:.3f}"))
    same = P[P.open & P.sym.isin(["USDJPY", "GBPJPY", "AUDJPY"])]; a3 = same[(same.index.year >= 2023) & (same.index.year <= 2025)].net.groupby(level=0).mean(); b3 = same[same.index.year == 2026].net.groupby(level=0).mean(); t3 = sps.ttest_ind(a3, b3, equal_var=False)
    summ.append(dict(item="同じ 3 通貨(USDJPY・GBPJPY・AUDJPY)だけで比べた場合", value=f"{a3.mean() * 1e4:.2f} 対 {b3.mean() * 1e4:.2f} bps、差の t = {t3.statistic:.2f}, p = {t3.pvalue:.3f}"))
    last = P.index.max()
    for s in PAIRS:
        x = P[P.sym == s].iloc[-1]; be = float(x.cost) * 1e4 * 360 / 3 / 100; summ.append(dict(item=f"現在({last.date()})の {s}", value=f"金利差 {x['diff']:.2f}pp, 門 {'開' if x.open else '閉'}, 理論値 {x.theory * 1e4:.2f} bps, コスト {x.cost * 1e4:.2f} bps, 理論値だけなら損益 0 になる金利差 {be:.2f}pp"))
    summ.append(dict(item="政策金利の表の最後の値", value=", ".join(f"{c} {RATES[c][-1][1]}({RATES[c][-1][0]})" for c in ("USD", "EUR", "GBP", "AUD", "CAD", "JPY"))))
    S = pd.DataFrame(summ); S.to_csv("results/q251_roll_shrink_summary.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 200)
    print("Q251(診断・セル 0) データ末尾", last.date()); print(D.to_string(index=False)); print()
    for _, r in S.iterrows(): print("-", r["item"], ":", r["value"])
