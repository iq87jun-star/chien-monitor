# FN Risk Limit(同時保有の SL リスク合計 3%・docs/241 §1ao)の実測。ops_inbox/<口座>/positions.csv から、同時に開いていた建玉の「建値→SL」損失額合計(初期残高比 %)を週ごとに出す。
# 使い方: cd research && python3 -W ignore forward/fn_sl_risk.py
import pandas as pd, numpy as np, sys
import os
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ops_inbox")
cols = ["ot","ticket","sym","side","lots","op","sl","tp","ct","cp","swap","comm","profit","comment","magic","slhit","x"]
def load(acc):
    d = pd.read_csv(f"{base}/{acc}/positions.csv", header=None, names=cols, encoding="utf-8-sig")
    d = d[pd.to_numeric(d.lots, errors="coerce").notna()].copy()
    for c in ["lots","op","sl","cp","profit"]: d[c] = pd.to_numeric(d[c])
    d["ot"] = pd.to_datetime(d.ot, format="%Y.%m.%d %H:%M:%S"); d["ct"] = pd.to_datetime(d.ct, format="%Y.%m.%d %H:%M:%S", errors="coerce")
    sgn = np.where(d.side.str.lower().str.startswith("b"), 1, -1)
    mv = (d.cp - d.op) * sgn * d.lots
    d["f"] = np.where(mv.abs() > 0, d.profit / mv, np.nan)        # 口座通貨 / (価格 1 × 1 lot)
    med = d.groupby("sym").f.median()
    d["f"] = d.f.where((d.f > 0) & (d.f / d.sym.map(med)).between(0.8, 1.25), d.sym.map(med))
    d["risk"] = np.where(d.sl > 0, (d.op - d.sl) * sgn * d.lots * d.f, np.nan)
    return d
def series(d, init):
    ev = sorted(set(d.ot))
    rows = []
    for t in ev:
        o = d[(d.ot <= t) & ((d.ct > t) | d.ct.isna())]
        rows.append((t, len(o), o.risk.clip(lower=0).sum() / init * 100, int(o.risk.isna().sum()), o.risk.max() / init * 100 if len(o) else 0))
    return pd.DataFrame(rows, columns=["t","n","cumrisk_pct","noSL","max_single_pct"])
for acc, init in [("11988011", 20000), ("14074882", 100000), ("14166201", 100000)]:
    d = load(acc); s = series(d, init)
    print(f"=== {acc} init={init} trades={len(d)} noSL trades={int((d.sl<=0).sum())}  period {d.ot.min().date()}..{d.ot.max().date()}")
    s["wk"] = s.t.dt.to_period("W-SUN")
    g = s.groupby("wk").agg(peak=("cumrisk_pct","max"), n=("n","max"), noSL=("noSL","max"), single=("max_single_pct","max"))
    print(g.round(2).tail(12).to_string())
    print("over 3% weeks:", int((g.peak > 3).sum()), "/", len(g), " over 1%:", int((g.peak > 1).sum()))
    if acc == "11988011":
        print(s[s.t >= "2026-11-09"].round(2).to_string(index=False))
    if (d.sl <= 0).any():
        print(d[d.sl <= 0].groupby(["sym","comment"]).size().tail(12).to_string())
