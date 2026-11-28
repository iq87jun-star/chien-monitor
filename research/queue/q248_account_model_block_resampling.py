# -*- coding: utf-8 -*-
"""docs/244 Q248(診断・セル 0・2026-11-16 登録): 口座モデルの週の引き方を、連続した週を続けて引く形に替えて、4 口座(FN Instant・トパーズ・ルビー・パール)の「現行 対 E1」の結論が変わるかを見る。
各週、確率 1/L で新しい週を無作為に引き、それ以外は前に引いた週の次の週を使う(L = 1・4・13。L = 1 は元のモデルと同じ乱数の並びになり、Q233 / Q234 の値と一致する)。
モデル・場面・開始残高・停止線・判定は Q233 / Q234 と同じ(両スクリプトの前半を読み込み、週を引く 1 行だけを差し替える)。
使い方: cd research && python3 -W ignore queue/q248_account_model_block_resampling.py   出力: results/q248_block_funded.csv・_eval.csv・_instant.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BLK = {"L": 1, "prev": None}; OLD = "idx = rng.integers(0, n, n_paths)"; NEW = "idx = _blk(rng, n, n_paths, w)"
def _blk(rng, n, n_paths, w):
    L = BLK["L"]
    if w == 0 or L <= 1: BLK["prev"] = rng.integers(0, n, n_paths)
    else: new = rng.random(n_paths) < 1.0 / L; BLK["prev"] = np.where(new, rng.integers(0, n, n_paths), (BLK["prev"] + 1) % n)
    return BLK["prev"]
def head(fn, marker, n_expected):
    s = open(os.path.join(HERE, fn), encoding="utf-8").read().split(marker)[0]; assert s.count(OLD) == n_expected, (fn, s.count(OLD)); ns = {"__name__": fn[:4] + "_head", "__file__": os.path.join(HERE, fn), "_blk": _blk}; exec(compile(s.replace(OLD, NEW), fn[:4] + "_head", "exec"), ns); return ns
n3 = head("q233_exit_switch_line_vs_vix_account_model.py", "\n# ---------------- (A) 本口座後", 2)
norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, MODE, PM, NP = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "MODE", "PM", "NP"))
LS = (1, 4, 13); MODES = (("現行(24h)", None), ("E1", "E1"))
def fund_ok(b, v): return bool((v["s10"] >= b["s10"] + 3.0 and v["p10"] >= b["p10"]) or (v["p10"] >= b["p10"] + 3.0 and v["s10"] >= b["s10"] - 1.0 and v["w2s5"] >= b["w2s5"] - 1.0))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
A = [("トパーズ", "6104739", None, True, False, 0.5, 0.01, 3.0, 4.5), ("ルビー / パール", "6104736", None, False, False, 0.5, 0.01, 2.78, 4.5)]
rows = []
for nm, key, capov, skew, trail, lo, pad, mm, rw in A:
    items, cap, g = norm_items(key); cap = cap if capov == "acct" else capov; fac = make_fac(items, skew, lo)
    for mn, md in MODES:
        MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
        for L in LS:
            BLK["L"] = L; r = dict(acct=nm, mode=mn, L=L)
            for tag in ("lo", "cl"):
                m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
            rows.append(r)
    print("A done", nm, flush=True)
DA = pd.DataFrame(rows)
for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DA[c] = DA[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
DA["E1_candidate"] = ""
for (nm, L), x in DA.groupby(["acct", "L"], sort=False): DA.loc[x.index[1], "E1_candidate"] = "変更候補" if fund_ok(x.iloc[0], x.iloc[1]) else "現行どおり"
DA.to_csv("results/q248_block_funded.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print("\n== 本口座後(存続 1 / 5 / 10 年 %・2016〜21 年のみ 5 年存続・累計出金 5 / 10 年 %) =="); print(DA[["acct", "mode", "L", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "E1_candidate"]].to_string(index=False), flush=True)
B = [("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 37535714 / 35e6 - 1, 0.08, 0.01, None), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None),
     ("ルビー", "6104736", "いま", 8.35, False, True, 0.5, False, 10348782 / 1e7 - 1, 0.08, 0.01, None), ("ルビー", "6104736", "次(8.35 倍)", 8.35, False, True, 0.5, False, 0.0, 0.06, 0.01, None), ("ルビー", "6104736", "次(6.3 倍)", 6.3, False, True, 0.5, False, 0.0, 0.06, 0.01, None),
     ("パール", "6071612", "いま", 5.57, False, False, None, False, 5291106 / 5e6 - 1, 0.08, 0.01, None), ("パール", "6071612", "次", 5.57, False, True, 0.5, False, 0.0, 0.06, 0.01, None)]
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None; fac = make_fac(items, skew, 0.5 if tilt else None)
    for mn, md in MODES:
        MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None
        for L in LS:
            BLK["L"] = L; r = dict(acct=nm, stage=stage, mode=mn, L=L)
            for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]
                r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
            rowsB.append(r)
    print("B done", nm, stage, flush=True)
DB = pd.DataFrame(rowsB); DB["E1_candidate"] = ""
for (nm, st, L), x in DB.groupby(["acct", "stage", "L"], sort=False): DB.loc[x.index[1], "E1_candidate"] = "変更候補" if ev_ok(x.iloc[0], x.iloc[1]) else "現行どおり"
DB.to_csv("results/q248_block_eval.csv", index=False); print("\n== 評価中(到達 % / 失格 % / 中央の週数) =="); print(DB.to_string(index=False), flush=True)
# ---------- FN Instant(Q234 のモデル) ----------
n4 = head("q234_apply_all_summary.py", "\nV = [(", 1); fxs, ixs, tot, MM, cap, g, SWAP, fac_state, sim, build, paths_fac, EXIT, P0, P1, PM4 = (n4[k] for k in ("fxs", "ixs", "tot", "MM", "cap", "g", "SWAP", "fac_state", "sim", "build", "paths_fac", "EXIT", "P0", "P1", "PM"))
rowsC = []
for nm, swap, fidx, m3 in (("現行", False, False, False), ("E1", False, False, "E1"), ("E1 + 指数の差し替え(11/18 の形)", True, True, "E1")):
    it = [(s, False, w / tot * MM) for s, w in fxs] + [((SWAP[s] if swap else s), True, w / tot * MM) for s, w in ixs]; fac = {(s, False): fac_state(s, False, 0.5) for s, w in fxs}
    if fidx: fac.update({(s, True): fac_state(s, True, 0.5) for s, i, w in it if i})
    EXIT["fx"] = m3; EXIT["idx"] = fidx; T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, fac, P0, P1), g, None); EXIT["fx"] = EXIT["idx"] = False; dates = pd.DatetimeIndex(dates); call = np.arange(len(dates)); c2 = call[dates < PM4]
    for L in LS:
        BLK["L"] = L; r = dict(variant=nm, L=L)
        for tag in ("lo", "cl"):
            m = sim(T[tag], call, 0.5, 520, 20000); m2 = sim(T[tag], c2, 0.5, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
        rowsC.append(r)
    print("C done", nm, flush=True)
DC = pd.DataFrame(rowsC)
for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DC[c] = DC[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
DC["vs_current"] = ""
for L, x in DC.groupby("L", sort=False):
    for i in x.index[1:]: DC.loc[i, "vs_current"] = "変更候補" if fund_ok(x.iloc[0], DC.loc[i]) else "現行どおり"
DC.to_csv("results/q248_block_instant.csv", index=False); print("\n== FN Instant(存続 1 / 5 / 10 年 %・2016〜21 年のみ 5 年存続・累計出金 5 / 10 年 %) =="); print(DC[["variant", "L", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "vs_current"]].to_string(index=False))
