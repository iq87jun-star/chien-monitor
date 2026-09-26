# -*- coding: utf-8 -*-
"""docs/311 Q68(F25): 東京窓(月曜 00→07 UTC)の符号による Mon の途中判断。
 新規 14: 7 ペア × {東京窓 陰線の週のみ, 陽線の週のみ} の 07:00→翌 07:00 LONG(3pip)
 改良系 2: Mon4 / Mon2(4 ショット 24h)で「07:00 時点の東京窓が −1×ATR24 超なら 04/06 ショットを 07:00 で手仕舞い・08/10 は建てない」
使い方: python3 queue/q68_tokyo_window_decision.py <累積>"""
import sys, os
from q_common import *
from q_cal import improved
def H(sym): df = load(sym); return df
def tokyo(sym):
    df = H(sym); o = df["open"]; mon = o.index[(o.index.dayofweek == 0) & (o.index.hour == 0)]
    t7 = mon + pd.Timedelta(hours=7); tw = pd.Series(o.reindex(t7).values / o.reindex(mon).values - 1.0, index=mon.normalize())
    atr = (df["high"] - df["low"]).rolling(24).mean().shift(1); a7 = pd.Series(atr.reindex(t7).values / o.reindex(mon).values, index=mon.normalize())
    return tw.dropna(), a7
def win_leg(sym, sel_days):
    df = H(sym); o = df["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == 7)]; t = t[t.normalize().isin(sel_days)]
    return trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values)
def shots(sym, guard):
    df = H(sym); o = df["open"]; tw, a7 = tokyo(sym); out = None
    for h in (4, 6, 8, 10):
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; d = t.normalize()
        bad = (tw.reindex(d).values < -a7.reindex(d).values) if guard else np.zeros(len(t), bool)
        px_out = o.reindex(t + pd.Timedelta(hours=24)).values.copy()
        if guard:
            if h in (4, 6): px_out[bad] = o.reindex(t[bad] + pd.Timedelta(hours=7 - h)).values   # 07:00 で手仕舞い
        keep = ~(bad & (h in (8, 10))) if guard else np.ones(len(t), bool)
        r = trades(sym, t[keep], o.reindex(t[keep]).values, np.ones(int(keep.sum())), px_out[keep]) / 4; r.index = r.index.normalize()
        out = r if out is None else out.add(r, fill_value=0)
    return out
cum = int(sys.argv[1]); R = Runner("Q68", cum, 16, "results/q68_tokyo_window_decision.csv"); diag = []
for p in base.MON_FX:
    tw, a7 = tokyo(p); neg = tw.index[tw < 0]; pos = tw.index[tw > 0]
    rn, rp = win_leg(p, neg), win_leg(p, pos)
    R.add("東京窓 陰線の週のみ 07→翌07 L", p, "東京 00-07 が陰線", rn); R.add("東京窓 陽線の週のみ 07→翌07 L", p, "東京 00-07 が陽線", rp)
    diag.append(dict(pair=p, neg_n=len(rn), neg_bps=round(float(rn.mean()) * 1e4, 2), pos_n=len(rp), pos_bps=round(float(rp.mean()) * 1e4, 2), bad_weeks=int((tw < -a7.reindex(tw.index)).sum())))
W = {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}}; imp = []
for nm, w in W.items():
    b = None; v = None
    for p, wt in w.items():
        sb = shots(p, False) * wt; sv = shots(p, True) * wt
        b = sb if b is None else b.add(sb, fill_value=0); v = sv if v is None else v.add(sv, fill_value=0)
    R.add(f"{nm} 東京窓ガード(改良系)", nm, "07:00 に東京窓 < −1×ATR24 なら 04/06 手仕舞い・08/10 見送り", v); imp.append(dict(comp=nm, **improved(b, v)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q68 診断(07→翌07 LONG・bps)==\n" + pd.DataFrame(diag).to_string(index=False)); print("\n== Q68 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
