# -*- coding: utf-8 -*-
"""docs/244 Q246(診断・セル 0・2026-11-16 登録): 指数レグの数量を 現行 / 半分 / なし にした形を、指数を持つ口座(トパーズ・1-Step)の口座モデルで比べる。円クロス・ロールは不変。
モデル・場面・開始残高・乱数・停止線・判定は Q233 と同じ(スクリプトは Q233 の前半をそのまま読み込み、指数の数量だけを変える)。トパーズの決済は E1、1-Step は 24h。FN Instant は q246b。
使い方: cd research && python3 -W ignore queue/q246_index_ratio_account_model.py   出力: results/q246_index_ratio_funded.csv・_eval.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd = n3["np"], n3["pd"]; norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, one_week_stats, MODE, PM, NP = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "one_week_stats", "MODE", "PM", "NP"))
KS = ((1.0, "現行"), (0.5, "指数 半分"), (0.0, "指数 なし"))
def scale_idx(items, k): return [(s, i, (w * k if i else w)) for s, i, w in items if not (i and k == 0.0)]
def fund_ok(b, v): return bool((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
# (A) 本口座後: 表示名, 口座キー, cap, SKEW, 追随型, 線の上の倍率, 停止線の手前幅, 円クロス倍率, ロール, 決済(Q233 の A と同じ行)
A = [("トパーズ", "6104739", None, True, False, 0.5, 0.01, 3.0, 4.5, "E1"), ("1-Step", "531466484", "acct", True, True, None, 0.01, 2.43, 0.0, None)]
rows = []
for nm, key, capov, skew, trail, lo, pad, mm, rw, md in A:
    items0, cap, g = norm_items(key); cap = cap if capov == "acct" else capov; print(nm, "構成(円クロスの合計 = 1):", [(s, i, round(w, 4)) for s, i, w in items0], flush=True)
    for k, kn in KS:
        items = scale_idx(items0, k); fac = make_fac(items, skew, lo); MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
        r = dict(acct=nm, variant=kn, k=k, mon=mm, roll=rw, **one_week_stats(T, dates))
        for tag in ("lo", "cl"):
            m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000)
            r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
        rows.append(r); print("A done", nm, kn, flush=True)
DA = pd.DataFrame(rows)
for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DA[c] = DA[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
DA["verdict"] = ""
for nm, x in DA.groupby("acct", sort=False):
    b = x.iloc[0]
    for i in x.index: DA.loc[i, "verdict"] = "—" if i == x.index[0] else ("変更候補" if fund_ok(b, DA.loc[i]) else "現行どおり")
DA.to_csv("results/q246_index_ratio_funded.csv", index=False)
print("\n== (A) 本口座後(1 年 / 5 年 / 10 年存続 %・2016〜21 年のみ 5 年存続・累計出金 5 年 / 10 年 %) =="); print(DA[["acct", "variant", "wk_mean_cl", "wk_sd_cl", "guard_cl", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "verdict"]].to_string(index=False))
# (B) 評価中: 表示名, 口座キー, 段階, 円クロス倍率, SKEW, 200 日線, 縮小の下限, 追随型, 開始, 目標, 停止線の手前幅, cap, 決済(Q233 の B と同じ行)
B = [("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 37535714 / 35e6 - 1, 0.08, 0.01, None, "E1"), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("1-Step", "531466484", "いま", None, True, False, None, True, 102722 / 1e5 - 1, 0.10, 0.01, "acct", None)]
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, md in B:
    items0, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    for k, kn in KS:
        items = scale_idx(items0, k); fac = make_fac(items, skew, 0.5 if tilt else None); MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; r = dict(acct=nm, stage=stage, variant=kn, k=k, mon=round(mm, 2), **one_week_stats(T, dates))
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]
            r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        rowsB.append(r); print("B done", nm, stage, kn, flush=True)
DB = pd.DataFrame(rowsB); DB["verdict"] = ""
for (nm, stage), x in DB.groupby(["acct", "stage"], sort=False):
    b = x.iloc[0]
    for i in x.index: DB.loc[i, "verdict"] = "—" if i == x.index[0] else ("変更候補" if ev_ok(b, DB.loc[i]) else "現行どおり")
DB.to_csv("results/q246_index_ratio_eval.csv", index=False)
print("\n== (B) 評価中(到達 % / 失格 % / 中央の週数。W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07) =="); print(DB[["acct", "stage", "variant", "mon", "wk_mean_cl", "wk_sd_cl", "guard_cl", "guard_lo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "verdict"]].to_string(index=False))
