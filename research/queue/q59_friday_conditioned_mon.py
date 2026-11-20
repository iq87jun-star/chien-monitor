# -*- coding: utf-8 -*-
"""docs/304 Q59(F16): 金曜条件付き Mon。Mon7 等ウェイト × {金曜陽線の週のみ, 陰線の週のみ, 金曜の値幅上位 1/3 を除外(改良系)} + 週末ギャップ {正のみ, 負のみ} = 5。
条件はペアごとの自分の金曜(前週末)リターン・ギャップで判定し、合成は該当ペアだけ。使い方: python3 queue/q59_friday_conditioned_mon.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
D = {p: base.load_daily(p) for p in base.MON_FX}; M = {p: base.mon_cell(p) for p in base.MON_FX}
def cond_series(fn):   # fn(p, t) -> bool
    out = None
    for p in base.MON_FX:
        m = M[p]; sel = pd.Series([bool(fn(p, t)) for t in m.index], index=m.index); x = m[sel] / 7.0
        out = x if out is None else out.add(x, fill_value=0.0)
    return out
# Yahoo 日足は FX の始値=終値のゼロ日が 35% あるため(データ品質)、金曜リターンと週末ギャップは Dukascopy H1 から取る(無ければ日足)
H1 = {}
for p in base.MON_FX:
    try: H1[p] = load(p)
    except Exception: H1[p] = None
def fri_ret(p, t):
    h = H1[p]
    if h is None:
        d = D[p]; prev = d.index[d.index < t]
        return float(d.loc[prev[-1], "close"] / d.loc[prev[-1], "open"] - 1.0) if len(prev) else np.nan
    f = (pd.Timestamp(t) - pd.Timedelta(days=3)).normalize(); x = h[(h.index >= f) & (h.index < f + pd.Timedelta(days=1))]
    return float(x["close"].iloc[-1] / x["open"].iloc[0] - 1.0) if len(x) >= 5 else np.nan
def gap(p, t):
    h = H1[p]
    if h is None:
        d = D[p]; prev = d.index[d.index < t]
        return float(d.loc[t, "open"] / d.loc[prev[-1], "close"] - 1.0) if (len(prev) and t in d.index) else np.nan
    f = (pd.Timestamp(t) - pd.Timedelta(days=3)).normalize(); x = h[(h.index >= f) & (h.index < f + pd.Timedelta(days=1))]; m = h[(h.index >= pd.Timestamp(t).normalize()) & (h.index < pd.Timestamp(t).normalize() + pd.Timedelta(hours=4))]
    return float(m["open"].iloc[0] / x["close"].iloc[-1] - 1.0) if (len(x) >= 5 and len(m)) else np.nan
FR = {p: pd.Series({t: fri_ret(p, t) for t in M[p].index}) for p in base.MON_FX}
thr = {p: FR[p][(FR[p].index >= IS0) & (FR[p].index <= IS1)].abs().quantile(2 / 3) for p in base.MON_FX}   # 上位 1/3 の閾値は IS で決める
cum = int(sys.argv[1]); R = Runner("Q59", cum, 5, "results/q59_friday_conditioned_mon.csv"); base7 = mon7()
cells = [("金曜陽線の週のみ", lambda p, t: FR[p].get(t, np.nan) > 0), ("金曜陰線の週のみ", lambda p, t: FR[p].get(t, np.nan) < 0),
         ("金曜値幅上位1/3を除外(改良系)", lambda p, t: abs(FR[p].get(t, np.nan)) <= thr[p]), ("週末ギャップ正のみ", lambda p, t: gap(p, t) > 0), ("週末ギャップ負のみ", lambda p, t: gap(p, t) < 0)]
rows = []
for name, fn in cells:
    s = cond_series(fn); R.add(name, "Mon7", name, s)
    if "改良" in name: rows.append(dict(cell=name, **improved(base7, s)))
R.finish(); print("\n== Q59 改良判定 ==\n" + pd.DataFrame(rows).to_string(index=False))
