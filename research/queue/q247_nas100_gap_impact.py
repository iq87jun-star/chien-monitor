# -*- coding: utf-8 -*-
"""docs/244 Q247(診断・セル 0・2026-11-16 登録): NAS100 の 1 時間足の欠け(124 か月中 38 か月)の影響の確認。
(a) US500 の月曜 13 UTC 24h と Mon4(24h)を、NAS100 に足がある週 / 無い週で比べる。(b) NAS100 のレグを US500 × β で代用して、Q246 の場面(トパーズ・1-Step × 指数 現行 / 半分 / なし)とトパーズの決済(現行 / E1)を取り直す。
β = 両方に足がある月曜の 24h 損益のばらつきの比(NAS100 / US500)。参考 β = 1。モデル・場面・乱数・判定は Q233 / Q246 と同じ。
使い方: cd research && python3 -W ignore queue/q247_nas100_gap_impact.py   出力: results/q247_nas100_gap_weeks.csv・_funded.csv・_eval.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, one_week_stats, MODE, PM, NP = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "one_week_stats", "MODE", "PM", "NP"))
sys.path.insert(0, HERE)
from q240_weekend_premium_predictions import idx_shot, frame, series
# ---------- (a) 欠けた週は特別か ----------
nas = idx_shot("NAS100", 0); us = idx_shot("US500", 0); us = us[us.index >= q.PRE0]; has = us.index.isin(nas.index); both = us.index[has]; BETA = float(nas.reindex(both).std() / us.reindex(both).std()); M4 = series(frame(), "base")
rowsA = []
for w, a, b in (("前窓", q.PRE0, q.IS0 - pd.Timedelta(hours=1)), ("IS", q.IS0, q.IS1), ("OOS", q.OOS0, q.END), ("全期間", q.PRE0, q.END)):
    for gn, m in (("NAS100 に足がある週", has), ("NAS100 に足が無い週", ~has)):
        x = us[m & (us.index >= a) & (us.index <= b)]; y = M4.reindex(x.index).dropna(); n1 = nas.reindex(x.index).dropna()
        rowsA.append(dict(window=w, group=gn, weeks=len(x), us500_mean_bps=round(float(x.mean()) * 1e4, 1) if len(x) else None, us500_sd_bps=round(float(x.std()) * 1e4, 1) if len(x) > 1 else None, us500_worst_bps=round(float(x.min()) * 1e4, 0) if len(x) else None, mon4_mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, mon4_sd_bps=round(float(y.std()) * 1e4, 1) if len(y) > 1 else None, nas100_mean_bps=round(float(n1.mean()) * 1e4, 1) if len(n1) else None, nas100_sd_bps=round(float(n1.std()) * 1e4, 1) if len(n1) > 1 else None))
WA = pd.DataFrame(rowsA); WA.to_csv("results/q247_nas100_gap_weeks.csv", index=False); print(f"β(NAS100 / US500 のばらつきの比・重なる {len(both)} 週)= {BETA:.3f}  相関 {float(np.corrcoef(nas.reindex(both), us.reindex(both))[0, 1]):.2f}"); print(WA.to_string(index=False), flush=True)
# ---------- (b) 口座モデルの取り直し ----------
def sub(items, beta):
    """NAS100 のレグを US500 × beta に置き換える(US500 が既にあれば足す)。beta = None は元のまま。"""
    if beta is None: return items
    out = {}; 
    for s, i, w in items:
        k = ("US500", True) if (i and s == "NAS100") else (s, i); out[k] = out.get(k, 0.0) + (w * beta if (i and s == "NAS100") else w)
    return [(s, i, w) for (s, i), w in out.items()]
def scale_idx(items, k): return [(s, i, (w * k if i else w)) for s, i, w in items if not (i and k == 0.0)]
def fund_ok(b, v): return bool((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
DATA = ((None, "元のデータ(欠けあり)"), (BETA, f"NAS100 → US500 × {BETA:.2f}"), (1.0, "NAS100 → US500 × 1.00(参考)"))
A = [("トパーズ", "6104739", None, True, False, 0.5, 0.01, 3.0, 4.5), ("1-Step", "531466484", "acct", True, True, None, 0.01, 2.43, 0.0)]
def run_f(nm, key, capov, skew, trail, lo, pad, mm, rw, md, beta, dn, k, kn):
    items0, cap, g = norm_items(key); cap = cap if capov == "acct" else capov; items = scale_idx(sub(items0, beta), k); fac = make_fac(items, skew, lo); MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
    r = dict(acct=nm, data=dn, exit=(md or "24h"), variant=kn, **one_week_stats(T, dates))
    for tag in ("lo", "cl"):
        m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
    return r
rows = []
for nm, key, capov, skew, trail, lo, pad, mm, rw in A:
    for beta, dn in DATA:
        for md in (("E1", None) if nm == "トパーズ" else (None,)):
            for k, kn in ((1.0, "指数 現行"), (0.5, "指数 半分"), (0.0, "指数 なし")):
                if (beta == 1.0 or md is None and nm == "トパーズ") and k != 1.0: continue          # 参考の行は「指数 現行」だけ
                if k == 0.0 and beta is not None: continue                                          # 指数なしは代用しても同じ
                rows.append(run_f(nm, key, capov, skew, trail, lo, pad, mm, rw, md, beta, dn, k, kn)); print("A done", nm, dn, md, kn, flush=True)
DA = pd.DataFrame(rows)
for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DA[c] = DA[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
DA.to_csv("results/q247_nas100_gap_funded.csv", index=False); print("\n== (b) 本口座後(存続 1 / 5 / 10 年 %・2016〜21 年のみ 5 年存続・累計出金 5 / 10 年 %) =="); print(DA[["acct", "data", "exit", "variant", "wk_mean_cl", "wk_sd_cl", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5"]].to_string(index=False), flush=True)
B = [("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 37535714 / 35e6 - 1, 0.08, 0.01, None), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None), ("1-Step", "531466484", "いま", None, True, False, None, True, 102722 / 1e5 - 1, 0.10, 0.01, "acct")]
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm in B:
    items0, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    for beta, dn in DATA:
        for md in (("E1", None) if nm == "トパーズ" else (None,)):
            for k, kn in ((1.0, "指数 現行"), (0.5, "指数 半分"), (0.0, "指数 なし")):
                if (beta == 1.0 or md is None and nm == "トパーズ") and k != 1.0: continue
                if k == 0.0 and beta is not None: continue
                items = scale_idx(sub(items0, beta), k); fac = make_fac(items, skew, 0.5 if tilt else None); MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; r = dict(acct=nm, stage=stage, data=dn, exit=(md or "24h"), variant=kn, **one_week_stats(T, dates))
                for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                    cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]
                    r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
                rowsB.append(r); print("B done", nm, stage, dn, md, kn, flush=True)
DB = pd.DataFrame(rowsB); DB.to_csv("results/q247_nas100_gap_eval.csv", index=False); print("\n== (b) 評価中(到達 % / 失格 % / 中央の週数) =="); print(DB[["acct", "stage", "data", "exit", "variant", "wk_mean_cl", "wk_sd_cl", "guard_lo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2"]].to_string(index=False))
