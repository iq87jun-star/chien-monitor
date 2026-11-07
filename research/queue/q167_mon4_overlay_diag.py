# -*- coding: utf-8 -*-
"""診断(セル 0・2026-11-08 ユーザー「USD や EUR の両建てによる弱点の補いや強みの高まり等は検討できませんか」):
配備形 Mon4(4 通貨・4/6/8/10 UTC 建て 24h)の週次損益と、同じ月曜 o2o の EURUSD / GBPUSD / AUDUSD / USDJPY / USDCHF / XAUUSD の値動きの関係。
(1) 相関と、Mon4 の最悪 10% 月曜での各銘柄の平均 bps(弱点がどの通貨要因か)。(2) ヘッジ比率 k の感応: Mon4 + k×SHORT(EURUSD・GBPUSD・AUDUSD 等ウェイト)、+ k×LONG USDJPY、+ k×LONG XAUUSD。
注意: XAUUSD の H1 が 2021 年開始のため共通期間は 2021-01〜(前窓はほぼ無い)。判定には使わない(新規セルの設計材料)。
使い方: cd research && python3 queue/q167_mon4_overlay_diag.py"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from q_common import *
SYMS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")
def norm(v):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize(); return v.groupby(v.index).sum()
def o2o(sym):
    o = load(sym)["open"]; out = None
    for h in (4, 6, 8, 10):
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; t2 = t + pd.Timedelta(hours=24); ok = t2.isin(o.index); t, t2 = t[ok], t2[ok]
        r = pd.Series(o.reindex(t2).values / o.reindex(t).values - 1, index=t.normalize()); out = r if out is None else out + r
    return (out / 4).dropna()
def stats(x, lo, hi):
    y = x[(x.index >= lo) & (x.index <= hi)]; m = y.groupby(pd.PeriodIndex(y.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return dict(sharpe=round(float(y.mean() / y.std() * np.sqrt(52)), 2), worst=round(float(m.min()) * 100, 2), bps=round(float(y.mean()) * 1e4, 1))
if __name__ == "__main__":
    D = sum(norm(base.mon_cell(s)) * 0.25 for s in SYMS).dropna()
    H = {s: o2o(s) for s in ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAUUSD", "USDCHF", "EURJPY", "GBPJPY", "AUDJPY")}
    j = D.index
    for h in H.values(): j = j.intersection(h.index)
    D2 = D[j]; worst = D2 <= D2.quantile(0.10); rows = []
    for s, h in H.items():
        h2 = h[j]; rows.append(dict(sym=s, corr=round(float(np.corrcoef(D2, h2)[0, 1]), 2), mean_bps=round(float(h2.mean()) * 1e4, 1), worst10_bps=round(float(h2[worst].mean()) * 1e4, 1)))
    T = pd.DataFrame(rows); print(f"共通期間 {j.min().date()}〜{j.max().date()} 週 {len(j)}・Mon4 平均 {D2.mean()*1e4:.1f} bps・最悪 10% 週の Mon4 平均 {D2[worst].mean()*1e4:.1f} bps"); print(T.to_string(index=False))
    rsk = -(H["EURUSD"][j] + H["GBPUSD"][j] + H["AUDUSD"][j]) / 3; out = []
    for nm, leg, c in (("SHORT EUR/GBP/AUD vs USD", rsk, 3e-4), ("LONG USDJPY 追加", H["USDJPY"][j], 3e-4), ("LONG XAUUSD", H["XAUUSD"][j], 5e-4)):
        for k in (0.0, 0.25, 0.5, 1.0):
            x = D2 + k * (leg - c); out.append(dict(overlay=nm, k=k, **{f"IS_{a}": b for a, b in stats(x, IS0, IS1).items()}, **{f"OOS_{a}": b for a, b in stats(x, OOS0, END).items()}))
    O = pd.DataFrame(out); pd.set_option("display.width", 250); print(O.to_string(index=False))
    os.makedirs(os.path.join(os.path.dirname(HERE), "results"), exist_ok=True); T.to_csv(os.path.join(os.path.dirname(HERE), "results", "q167_mon4_overlay_corr.csv"), index=False); O.to_csv(os.path.join(os.path.dirname(HERE), "results", "q167_mon4_overlay_sens.csv"), index=False)
