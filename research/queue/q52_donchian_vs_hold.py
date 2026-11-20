# -*- coding: utf-8 -*-
"""docs/296 Q52(改良系): 指数ブレイク買い(Q16 の両窓プラスセル)を Hold(連続 LONG)の改良として判定。
 セル 1: NAS100 ドンチャン 24 本 高値更新で L・24h 固定  セル 2: GER40 ドンチャン 120 本 高値更新で L・2ATR トレイル。
 基準(docs/244 §1 改良系): IS・OOS の両方でベース(Hold)比 Sharpe 改善 かつ 最悪月が悪化しない。使い方: python3 queue/q52_donchian_vs_hold.py <累積>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
CELLS = [("NAS100", 24, "fixed24h"), ("GER40", 120, "trail2ATR")]; MAXH = 240
def donchian(sym, N, ex):
    df = load(sym); o = df["open"].values; c = df["close"].values; h = df["high"]; l = df["low"]; a = atr24(df).values; idx = df.index; n = len(df)
    hh = h.rolling(N).max().shift(1).values; trig = (c > hh) & ~np.isnan(a); t_in, p_in, p_out = [], [], []; i = 0
    for j in np.flatnonzero(trig):
        if j + 1 >= n or j + 1 < i: continue
        e = j + 1; atr = a[j]
        if ex == "fixed24h":
            x = e + 24
            if x >= n: break
        else:
            ext = c[e]; x = None
            for k in range(e, min(e + MAXH, n - 1)):
                ext = max(ext, c[k])
                if c[k] < ext - 2 * atr: x = k + 1; break
            if x is None: x = min(e + MAXH, n - 1)
        t_in.append(idx[e]); p_in.append(o[e]); p_out.append(o[x]); i = x
    return trades(sym, pd.DatetimeIndex(t_in), np.array(p_in), np.ones(len(t_in)), np.array(p_out))
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    sh = round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0
    return sh, round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1)
cum = int(sys.argv[1]); R = Runner("Q52", cum, len(CELLS), "results/q52_donchian_vs_hold.csv"); rows = []
for sym, N, ex in CELLS:
    r = donchian(sym, N, ex); d = r.groupby(r.index.normalize()).sum(); h = base.hold_cell(sym)
    BD = pd.bdate_range(max(d.index.min(), h.index.min()), min(d.index.max(), h.index.max())); d = d.reindex(BD).fillna(0.0); h = h.reindex(BD).fillna(0.0)
    R.add("指数ブレイク vs Hold(改良系)", sym, f"ドンチャン N={N} L exit={ex}", r)
    bi, bo, gi, go = stats(h, IS0, IS1), stats(h, OOS0, END), stats(d, IS0, IS1), stats(d, OOS0, END)
    ok = gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]
    yr = {y: (round(float((1 + h[h.index.year == y]).prod() - 1) * 100, 1), round(float((1 + d[d.index.year == y]).prod() - 1) * 100, 1)) for y in range(2021, 2027)}
    rows.append(dict(symbol=sym, cell=f"N={N} {ex}", hold_IS_sharpe=bi[0], brk_IS_sharpe=gi[0], hold_OOS_sharpe=bo[0], brk_OOS_sharpe=go[0], hold_IS_worst=bi[1], brk_IS_worst=gi[1], hold_OOS_worst=bo[1], brk_OOS_worst=go[1], hold_IS_ret=bi[2], brk_IS_ret=gi[2], hold_OOS_ret=bo[2], brk_OOS_ret=go[2], improved=ok))
    print(f"[{sym}] 年別 (Hold, ブレイク) %: " + ", ".join(f"{y}: {a:+.1f}/{b:+.1f}" for y, (a, b) in yr.items()))
R.finish(); pd.set_option("display.width", 300); print("\n== Q52 改良判定 ==\n" + pd.DataFrame(rows).to_string(index=False))
