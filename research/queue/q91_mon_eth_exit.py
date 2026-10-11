# -*- coding: utf-8 -*-
"""docs/322 Q91(改良系・4 セル): Mon ETHUSD の出口。現行は月曜 00:00 UTC 始値 → 翌 00:00 UTC 始値(24h・研究セル mon_cell と同じ日足 o2o)。
変種 {12h, 36h, 翌日 NY 引け(火曜 16:00 ET = 20/21 UTC), 24h+トレイル(直前 24 本 ATR 1 本分を高値から割ったら引ける・それ以外は 24h)} を
Dukascopy H1(2018〜2026-08)で基準と同じ往復 15 bps で比較。判定は docs/244 §1 改良系(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)。
トレイルの幅は事前固定(ATR24 × 1.0)で、格子探索はしない。使い方: cd research && python3 queue/q91_mon_eth_exit.py <累積セル数>"""
import sys, os
from q_common import *
SYM = "ETHUSD"; RT = 15e-4   # recentfit_screen.IDX_COST["ETHUSD"](往復)
def us_dst(ts):   # 3 月第 2 日曜 〜 11 月第 1 日曜(ET)。UTC 日付で近似(境界日の 2 時間差は無視)
    y = ts.year; m8 = pd.Timestamp(y, 3, 8); n1 = pd.Timestamp(y, 11, 1)
    mar = m8 + pd.Timedelta(days=(6 - m8.weekday()) % 7); nov = n1 + pd.Timedelta(days=(6 - n1.weekday()) % 7)
    return mar <= ts.normalize() < nov
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 1 and x.std() > 0 else 0.0), round(float(m.min()) * 100, 2), int(len(x))
def improved(basis, var):
    bi, bo, gi, go = stats(basis, IS0, IS1), stats(basis, OOS0, END), stats(var, IS0, IS1), stats(var, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))
df = load(SYM); df["atr24"] = atr24(df)
mons = df.index[(df.index.weekday == 0) & (df.index.hour == 0)]
def px_at(t):   # その時刻の始値(欠損なら直後のバー)
    i = df.index.searchsorted(t); return (df.index[i], float(df["open"].iloc[i])) if i < len(df) else (None, None)
rows = {k: [] for k in ("24h(現行)", "12h", "36h", "翌日NY引け", "24h+トレイル")}
for t0 in mons:
    e = float(df.at[t0, "open"])
    for k, dt_ in (("24h(現行)", pd.Timedelta(hours=24)), ("12h", pd.Timedelta(hours=12)), ("36h", pd.Timedelta(hours=36))):
        tx, px = px_at(t0 + dt_)
        if tx is not None and tx - t0 <= dt_ + pd.Timedelta(hours=3): rows[k].append((t0, px / e - 1 - RT))
    ny = t0 + pd.Timedelta(days=1, hours=(20 if us_dst(t0) else 21)); i = df.index.searchsorted(ny)
    if i < len(df) and df.index[i] - ny <= pd.Timedelta(hours=3): rows["翌日NY引け"].append((t0, float(df["close"].iloc[i]) / e - 1 - RT))
    w = df[(df.index > t0) & (df.index <= t0 + pd.Timedelta(hours=24))]; a = df.at[t0, "atr24"]
    if len(w) and np.isfinite(a) and a > 0:
        hi = e; out = None
        for ts, r in w.iterrows():
            hi = max(hi, float(r["high"]))
            if float(r["low"]) <= hi - a: out = hi - a; break
        if out is None:
            tx, px = px_at(t0 + pd.Timedelta(hours=24)); out = px
        if out is not None: rows["24h+トレイル"].append((t0, out / e - 1 - RT))
S = {k: pd.Series([v for _, v in r], index=pd.DatetimeIndex([t for t, _ in r])) for k, r in rows.items()}
base_s = S["24h(現行)"]; cum = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = []
for k in ("12h", "36h", "翌日NY引け", "24h+トレイル"):
    v = S[k]; idx = base_s.index.intersection(v.index); r = improved(base_s.loc[idx], v.loc[idx])
    pre_b, pre_v = stats(base_s.loc[idx], PRE0, IS0 - pd.Timedelta(hours=1)), stats(v.loc[idx], PRE0, IS0 - pd.Timedelta(hours=1))
    out.append(dict(variant=k, n=len(idx), base_IS=r["base_IS"], var_IS=r["var_IS"], base_OOS=r["base_OOS"], var_OOS=r["var_OOS"], pre_base=pre_b, pre_var=pre_v, improved=r["ok"]))
R = pd.DataFrame(out); pd.set_option("display.width", 250); print(f"Q91 {SYM} Mon 出口: 月曜 {len(base_s)} 本 ({base_s.index.min().date()}〜{base_s.index.max().date()})  累積 {cum} → {cum + 4}")
print(R.to_string(index=False)); R.to_csv("results/q91_mon_eth_exit.csv", index=False)
try:
    base.DATA = os.path.join(ROOT, "data_202609"); d = base.mon_cell(SYM); j = pd.concat([base_s.rename("h1"), d.rename("daily")], axis=1).dropna()
    print(f"参考: H1 基準 vs 日足 mon_cell の相関 {j.h1.corr(j.daily):.3f}(n={len(j)})")
except Exception as ex: print("参考(日足)なし:", repr(ex))
