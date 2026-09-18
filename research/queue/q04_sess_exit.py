# -*- coding: utf-8 -*-
"""docs/244 Q4: Sess 8 セルの出口改良。保有 {3,4,5,6}h × SL {15pip, 25pip, なし} = 12 変種 × 8 セル = 96(改良系・有意性検定なし)。
基準 = 研究定義(4h・SL なし・docs/235)。EA 近似 = 4h・SL15。判定: IS(2021-10〜2024-12)と OOS(2025-01〜末尾)の両方で Sharpe がベース比改善 かつ 最悪月が悪化しない。
SL は H1 の高値(SHORT)/安値(LONG)で判定し、SL 価格で約定(滑りなし・bid のみ = 楽観側)。往復 3pip。research/ で実行。"""
import os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
S8 = [("EURGBP", 20), ("NZDUSD", 20), ("AUDUSD", 20), ("EURGBP", 16), ("USDCHF", 0), ("USDCHF", 16), ("NZDUSD", 16), ("CHFJPY", 20)]   # 全て SHORT・月〜木
A, IS1, OOS0 = pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
HOLDS = (3, 4, 5, 6); SLS = (15, 25, None)
def pip(sym): return 0.01 if sym.endswith("JPY") else 0.0001
def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= A - pd.Timedelta(days=3))]
def cell(df, sym, h0, hold, sl_pips):
    o, h = df["open"], df["high"]; d = df[(df.index.hour == h0) & (df.index.dayofweek <= 3)]
    out = []; p = pip(sym)
    for t, px0 in d["open"].items():
        t1 = t + pd.Timedelta(hours=hold); seg = h[(h.index >= t) & (h.index < t1)]
        if len(seg) < hold: continue
        exit_px = o.get(t1, np.nan)
        if np.isnan(exit_px): continue
        if sl_pips is not None:
            slp = px0 + sl_pips * p; hit = seg[seg >= slp]
            if len(hit): exit_px = slp
        out.append((t, -(exit_px / px0 - 1.0) - 3 * p / px0))   # SHORT・往復 3pip
    return pd.Series([r for _, r in out], index=pd.DatetimeIndex([t for t, _ in out]))
def perf(r):
    if len(r) < 20: return dict(sharpe=np.nan, worst_m=np.nan, cum=np.nan, n=len(r))
    daily = r.groupby(r.index.floor("D")).sum(); m = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return dict(sharpe=round(float(daily.mean() / daily.std() * np.sqrt(252)), 2), worst_m=round(float(m.min()) * 100, 2), cum=round(float((1 + r).prod() - 1) * 100, 1), n=len(r))
rows = []; data = {s: load(s) for s in {s for s, _ in S8}}
for sym, h0 in S8:
    base_is = base_oos = None
    for hold in HOLDS:
        for sl in SLS:
            r = cell(data[sym], sym, h0, hold, sl); ri, ro = r[r.index <= IS1], r[r.index >= OOS0]
            pi, po = perf(ri), perf(ro)
            rows.append(dict(cell=f"{sym} {h0:02d}-{(h0+4)%24:02d}S", hold=hold, sl=("none" if sl is None else sl), is_sharpe=pi["sharpe"], is_worst_m=pi["worst_m"], is_cum=pi["cum"], oos_sharpe=po["sharpe"], oos_worst_m=po["worst_m"], oos_cum=po["cum"], n=pi["n"] + po["n"]))
R = pd.DataFrame(rows)
def flag(g):
    b = g[(g.hold == 4) & (g.sl == "none")].iloc[0]
    g = g.copy(); g["improve"] = (g.is_sharpe > b.is_sharpe) & (g.oos_sharpe > b.oos_sharpe) & (g.is_worst_m >= b.is_worst_m) & (g.oos_worst_m >= b.oos_worst_m); return g
R = R.groupby("cell", group_keys=False).apply(flag); R.to_csv("results/q4_sess_exit.csv", index=False)
pd.set_option("display.width", 220)
print("variants", len(R), "improve", int(R.improve.sum()))
print("\n== ベース(4h・SL なし)と EA 近似(4h・SL15)"); print(R[(R.hold == 4) & (R.sl.isin(["none", 15]))].to_string(index=False))
print("\n== 改善フラグ"); print(R[R.improve].to_string(index=False) if R.improve.any() else "(none)")
print("\n== 保有時間別の IS/OOS Sharpe 平均(SL なし)"); print(R[R.sl == "none"].groupby("hold")[["is_sharpe", "oos_sharpe", "is_worst_m", "oos_worst_m"]].mean().round(2).to_string())
print("\n== SL 別(4h)"); print(R[R.hold == 4].groupby("sl")[["is_sharpe", "oos_sharpe", "is_worst_m", "oos_worst_m"]].mean().round(2).to_string())
