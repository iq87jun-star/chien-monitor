# -*- coding: utf-8 -*-
"""docs/274: BROAD_IV(34 セル)から TSMOM 6 セルを除いた 28 セル、TSMOM 6 セル単独、との比較(ウォークフォワード・逆ボラ cap40%・倍率規則・MC FTMO/FN)。docs/187 と同じ機構(selection_metric_walkforward)。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import selection_value_walkforward as wf, selection_metric_walkforward as sm
SEED = 7
def build(include):
    cells = {}
    if "Mon" in include:
        for nm in base.MON_FX + base.MON_IDX: cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    if "Hold" in include:
        for nm in base.HOLD_SYMS: cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    if "TSMOM" in include:
        for nm in base.TSMOM_SYMS: cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    if "v4" in include:
        for p in base.V4_PAIRS: cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    return cells
base.W_ALL1 = pd.Timestamp("2026-08-31"); dates = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
out = {}; daily = {}
for name, inc in (("BROAD34", ("Mon", "Hold", "TSMOM", "v4")), ("BROAD28_noTSMOM", ("Mon", "Hold", "v4")), ("TSMOM6", ("TSMOM",))):
    cells = build(inc); base.verify_window([v["s"] for v in cells.values()])
    s, hist = sm.run(cells, "BROAD_IV", dates); daily[name] = s
    span = (s.index[-1] - s.index[0]).days; factor = span / len(s); md = int(round(365 / factor))
    rec = dict(cells=len(cells), **wf.perf(s), avg_mult=round(float(np.mean([h["mult"] for h in hist])), 2), sharpe_cal=round(float(s.mean() / s.std() * np.sqrt(365 / factor)), 2))
    for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
        base.P1_TARGET = p1; r = base.mc_challenge(s, 1.0, np.random.default_rng(SEED), max_days=md); rec[venue] = dict(funded=r.get("funded"), fail=r.get("fail"), days_med=int(round(r["funded_days_med"] * factor)) if r.get("funded_days_med") else None)
    out[name] = rec; print(name, json.dumps(rec, ensure_ascii=False, default=str), flush=True)
a, b = wf.monthly(daily["BROAD34"]), wf.monthly(daily["BROAD28_noTSMOM"]); idx = sorted(set(a.index) | set(b.index)); d = (a.reindex(idx).fillna(0) - b.reindex(idx).fillna(0)).values
t, p = wf.ttest_paired(d); print(f"BROAD34 − BROAD28: Δ={np.mean(d)*100:+.3f}%/月 t={t} p={p}")
m28, m6 = wf.monthly(daily["BROAD28_noTSMOM"]), wf.monthly(daily["TSMOM6"]); idx = sorted(set(m28.index) & set(m6.index)); print("月次相関(28 vs TSMOM6):", round(float(np.corrcoef(m28.reindex(idx), m6.reindex(idx))[0, 1]), 3))
json.dump(out, open(os.path.join(HERE, "results", "tsmom_ablation.json"), "w"), ensure_ascii=False, indent=1, default=str)
