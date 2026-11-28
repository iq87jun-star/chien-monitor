# -*- coding: utf-8 -*-
"""docs/244 Q246(診断・セル 0)の FN Instant 分: 11/18 に切り替える形(円クロスの決済 E1 + 指数 US30・JP225 の形 F)で、指数レグの数量を 現行 / 半分 / なし にして口座モデルで比べる。
モデル・開始残高・乱数・判定は Q234 (a) と同じ(スクリプトは Q234 の前半をそのまま読み込み、指数の数量だけを変える)。
使い方: cd research && python3 -W ignore queue/q246b_index_ratio_instant_account_model.py   出力: results/q246_index_ratio_instant.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q234_apply_all_summary.py"), encoding="utf-8").read().split("\nV = [(")[0]; n4 = {"__name__": "q234_head", "__file__": os.path.join(HERE, "q234_apply_all_summary.py")}; exec(compile(_src, "q234_head", "exec"), n4)
np, pd = n4["np"], n4["pd"]; fxs, ixs, tot, MM, cap, g, SWAP, fac_state, sim, build, paths_fac, EXIT, P0, P1, PM, NP = (n4[k] for k in ("fxs", "ixs", "tot", "MM", "cap", "g", "SWAP", "fac_state", "sim", "build", "paths_fac", "EXIT", "P0", "P1", "PM", "NP"))
rows = []
for k, kn in ((1.0, "現行(E1 + 指数 US30・JP225 の F)"), (0.5, "指数 半分"), (0.0, "指数 なし")):
    it = [(s, False, w / tot * MM) for s, w in fxs] + ([(SWAP[s], True, w / tot * MM * k) for s, w in ixs] if k > 0 else []); fac = {(s, False): fac_state(s, False, 0.5) for s, w in fxs}; fac.update({(s, True): fac_state(s, True, 0.5) for s, i, w in it if i})
    EXIT["fx"] = "E1"; EXIT["idx"] = True; T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, fac, P0, P1), g, None); EXIT["fx"] = EXIT["idx"] = False; dates = pd.DatetimeIndex(dates); call = np.arange(len(dates)); c2 = call[dates < PM]
    r = dict(variant=kn, k=k, items=str([(s, i, round(w, 4)) for s, i, w in it]), weeks=len(dates), wk_mean=round(float(T["cl"][0][-1].mean()) * 100, 3), wk_sd=round(float(T["cl"][0][-1].std()) * 100, 3), guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2))
    for tag in ("lo", "cl"):
        m = sim(T[tag], call, 0.5, 520, NP); m2 = sim(T[tag], c2, 0.5, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
    rows.append(r); print("done", kn, flush=True)
D = pd.DataFrame(rows)
for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): D[c] = D[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
b = D.iloc[0]; D["verdict"] = ["—"] + [("変更候補" if ((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0)) else "現行どおり") for _, v in D.iloc[1:].iterrows()]
D.to_csv("results/q246_index_ratio_instant.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 110)
print(D[["variant", "items"]].to_string(index=False)); print(D[["variant", "weeks", "wk_mean", "wk_sd", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "verdict"]].to_string(index=False))
