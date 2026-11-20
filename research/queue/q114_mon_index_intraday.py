# -*- coding: utf-8 -*-
"""docs/322 §5c Q114(改良系・4 セル): Mon 指数の日中版。月曜 13 UTC 建て(配備形は → 翌日 13 UTC の 24h)を「同日 20 UTC(16:00 ET 前)決済」に変えたとき、
US500 / NAS100 / US30 / JP225 で docs/244 §1 改良系基準(IS・OOS 両方で Sharpe 改善 かつ 最悪月が悪化しない)を満たすか。h14 は参照(セルに数えない)。
H1 Dukascopy・コストは q_common(指数 3 bps)。使い方: cd research && python3 queue/q114_mon_index_intraday.py <累積セル数>"""
import sys, os
from q_common import *
IDX = ["US500", "NAS100", "US30", "JP225"]; EXIT_H = 20
def shot(sym, h_in, h_out_same_day):
    df = load(sym); o = df["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h_in)]
    t_out = (t + pd.Timedelta(hours=24)) if h_out_same_day is None else pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out_same_day) for x in t])
    r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t_out).values); r.index = r.index.normalize(); return r
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 5 and x.std() > 0 else 0.0), round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1)
def improved(b, v):
    bi, bo, gi, go = stats(b, IS0, IS1), stats(b, OOS0, END), stats(v, IS0, IS1), stats(v, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q114", cum, len(IDX), "results/q114_mon_index_intraday.csv"); rows = []
    for sym in IDX:
        for h in (13, 14):
            b, v = shot(sym, h, None), shot(sym, h, EXIT_H)
            if h == 13: R.add("Mon 指数 日中版(改良系)", sym, "月曜 13 UTC 建て → 同日 20 UTC 決済(配備形 24h 比)", v)
            im = improved(b, v); rows.append(dict(symbol=sym, h=h, cell=("セル" if h == 13 else "参照"), **im))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q114_mon_index_intraday_levels.csv", index=False)
    print("\n== Q114 改良判定(Sharpe, 最悪月 %, 累積 %)==\n" + D.to_string(index=False)); print("\n改良成立(h13 セル):", int(D[D.h == 13].ok.sum()), "/ 4")
