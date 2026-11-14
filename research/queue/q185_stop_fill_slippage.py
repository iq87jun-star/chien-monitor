# -*- coding: utf-8 -*-
"""docs/244 Q185(診断・セル 0・2026-11-12 登録): 損切り・ガード発動時の滑りの実測(ops_inbox の positions.csv・2026-08〜11)。
 (a) ガードによる一斉決済(3 本以上が 10 秒以内・合計損失・保有 23.5h 未満・SL 約定でない)。(b) SL 約定の決済価格と SL 価格の差(不利方向を正)。
使い方: cd research && python3 -W ignore queue/q185_stop_fill_slippage.py   出力: results/q185_sl_fill_slippage.csv・_clusters.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
INIT = {"521100397": 50000, "531407058": 50000, "531343523": 1e5, "531466484": 1e5, "11988011": 2e4, "14074882": 1e5, "14166201": 1e5, "6071612": 5e6, "6104736": 1e7, "6104739": 35e6}
FIRM = {"521100397": "FTMO", "531407058": "FTMO", "531343523": "FTMO", "531466484": "FTMO", "11988011": "FundedNext", "14074882": "FundedNext", "14166201": "FundedNext", "6071612": "Fintokei", "6104736": "Fintokei", "6104739": "Fintokei"}
cols = ["ot", "ticket", "sym", "side", "lots", "op", "sl", "tp", "ct", "cp", "swap", "comm", "profit", "comment", "magic", "slhit", "x"]
def kind(s):
    s = s.upper().rstrip("P").replace(".CASH", "")
    if len(s) == 6 and s.isalpha() and not s.startswith(("XAU", "XAG", "BTC", "ETH", "USO", "UKO")): return "為替"
    if any(k in s for k in ("100", "500", "US30", "GER", "UK1", "JP2", "NDX", "SPX", "DAX")): return "指数"
    return "金属・原油・暗号資産"
A, C = [], []
for acc, init in INIT.items():
    d = pd.read_csv(f"ops_inbox/{acc}/positions.csv", header=None, names=cols, encoding="utf-8-sig"); d = d[pd.to_numeric(d.lots, errors="coerce").notna()].copy()
    for c in ("lots", "op", "sl", "cp", "profit"): d[c] = pd.to_numeric(d[c])
    d["ot"] = pd.to_datetime(d.ot, format="%Y.%m.%d %H:%M:%S"); d["ct"] = pd.to_datetime(d.ct, format="%Y.%m.%d %H:%M:%S", errors="coerce"); d["slhit"] = d.slhit.astype(str) == "True"
    d["acct"] = acc; d["firm"] = FIRM[acc]; d["kind"] = d.sym.astype(str).map(kind); sgn = np.where(d.side.astype(str).str.lower().str.startswith("b"), 1, -1)
    d["sl_dist"] = (d.op - d.sl) * sgn; d["slip"] = (d.sl - d.cp) * sgn                    # 正 = SL より不利な約定
    d["slip_ratio"] = d.slip / d.sl_dist; d["pip"] = np.where(d.sym.astype(str).str.upper().str.contains("JPY"), 0.01, np.where(d.kind == "為替", 0.0001, np.nan)); d["slip_pips"] = d.slip / d.pip
    A.append(d[d.slhit & (d.sl > 0)])
    x = d[(~d.slhit) & d.ct.notna()].copy(); x["hold_h"] = (x.ct - x.ot).dt.total_seconds() / 3600; x["grp"] = x.ct.dt.floor("10s")
    g = x.groupby("grp").agg(n=("ticket", "count"), pnl=("profit", "sum"), maxh=("hold_h", "max")); g = g[(g.n >= 3) & (g.pnl < 0) & (g.maxh < 23.5)]
    for t, r in g.iterrows(): C.append(dict(acct=acc, time=str(t), n=int(r.n), pnl_pct=round(r.pnl / init * 100, 2), max_hold_h=round(r.maxh, 1)))
S = pd.concat(A); S.to_csv("results/q185_sl_fill_slippage.csv", index=False, columns=["acct", "firm", "kind", "sym", "ot", "ct", "lots", "op", "sl", "cp", "sl_dist", "slip", "slip_ratio", "slip_pips", "profit"])
def summ(g):
    return pd.Series(dict(n=len(g), adverse_share=round(float((g.slip > 0).mean()), 2), slip_ratio_med=round(float(g.slip_ratio.median()) * 100, 2), slip_ratio_p95=round(float(g.slip_ratio.quantile(.95)) * 100, 2),
                          slip_ratio_max=round(float(g.slip_ratio.max()) * 100, 2), slip_pips_med=round(float(g.slip_pips.median()), 2) if g.slip_pips.notna().any() else np.nan,
                          slip_pips_max=round(float(g.slip_pips.max()), 2) if g.slip_pips.notna().any() else np.nan))
pd.set_option("display.width", 240)
print("SL 約定の件数:", len(S)); print(S.groupby(["firm", "kind"]).apply(summ).to_string()); print(); print(S.groupby("kind").apply(summ).to_string())
print("\n最大の滑り 5 件:"); print(S.nlargest(5, "slip_ratio")[["acct", "sym", "ct", "sl_dist", "slip", "slip_ratio", "profit"]].round(4).to_string(index=False))
Cd = pd.DataFrame(C); Cd.to_csv("results/q185_guard_clusters.csv", index=False); print("\nガード型の一斉決済(損失・3 本以上・24h 未満):", len(Cd)); print(Cd.to_string(index=False) if len(Cd) else "なし")
