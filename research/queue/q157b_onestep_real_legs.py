# -*- coding: utf-8 -*-
"""docs/400 Q157 補足: 1-Step 531466484 の帳簿を config の合成レグ(a9 = XAU/GBPJPY/NAS 各 1/3 + Mon4)ではなく EA9 v1.06 の実入力
(Mon GBPJPY 0.797・EURJPY/AUDJPY/USDJPY 各 0.167・NAS100 0.25・Hold XAU 0.12・×3.0。資金化後は ×1.25)で記述し、スワップ込みで Hold XAU の重みを比較する。
使い方: cd research && python3 -W ignore queue/q157b_onestep_real_legs.py → results/q157_onestep_real_legs.csv"""
import os, sys, json, copy
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import forward.portfolio_sim as ps
from forward.portfolio_sim import run_portfolio, summarize, book, R
N, SEED = 6000, 44; NAME = "1-Step 531466484"
def spec(mult, xau_w=0.12, xau_to_gbp=False):
    w = {"mon_gbpjpy": 0.797, "mon_eurjpy": 0.167, "mon_audjpy": 0.167, "mon_usdjpy": 0.167, "nas": 0.25, "holdxau": xau_w}
    if xau_to_gbp: w["mon_gbpjpy"] += 0.12; w["holdxau"] = 0.0
    return {k: round(v * mult, 4) for k, v in w.items() if v > 0}
def sharpe(sp, sw): x = R(book(sp, sw)); return float(x.mean() / x.std() * np.sqrt(252))
def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); rows = []
    base_eval = [a for a in cfg["accounts"] if a["name"] == NAME][0]
    cases = [("config 合成(a9+mon4)・swap 無", None, 0.0), ("config 合成(a9+mon4)・swap −52", None, -52.0)]
    for lab, xw, tg in (("実レグ XAU 0.12(現行)", 0.12, False), ("実レグ XAU 0.06(半分)", 0.06, False), ("実レグ XAU 0", 0.0, False), ("実レグ XAU→GBPJPY 置換", 0.12, True)):
        cases.append((lab + "・swap −52", (xw, tg), -52.0))
    cases.append(("実レグ XAU 0.12・swap 無", (0.12, False), 0.0))
    for lab, real, sw in cases:
        c = copy.deepcopy(cfg)
        for a in c["accounts"]:
            if a["name"] == NAME:
                if real is not None: a["eval"] = spec(3.0, *real); a["funded"] = spec(1.25, *real)
                a["swap_xau_bps_m"] = sw; ev, fu = a["eval"], a["funded"]
        res = run_portfolio(c, N=N, seed=SEED); s = summarize(res, lab); jpy, pct = res["per"][NAME]; st = res["stats"][NAME]
        r = dict(case=lab, eval=json.dumps(ev), funded=json.dumps(fu), xau_eval=ps.hold_xau_notional(ev), pay_mean_man=jpy.mean() / 1e4, pay_med_man=float(np.median(jpy)) / 1e4, zero=(jpy <= 0).mean() * 100,
                 reach=st["reach"] * 100, fail=st["fail"] * 100, fail_funded_of_reached=st["fail_funded_of_reached"] * 100, sharpe_eval=sharpe(ev, sw), total_mean=s["mean"], total_p16=s["p16"]); rows.append(r)
        print(f"{lab:<34} XAU名目(評価) {r['xau_eval']:.2f} | 期待 {r['pay_mean_man']:5.1f} 万/月 中央 {r['pay_med_man']:5.1f} 0率 {r['zero']:3.0f}% | 到達 {r['reach']:5.1f}% 失格 {r['fail']:5.1f}%(資金化後 {r['fail_funded_of_reached']:5.1f}) Sharpe {r['sharpe_eval']:.2f} | 全体 {s['mean']:.0f} / −1σ {s['p16']:.0f}")
    pd.DataFrame(rows).to_csv(os.path.join(ROOT, "results", "q157_onestep_real_legs.csv"), index=False); print("saved results/q157_onestep_real_legs.csv")
if __name__ == "__main__": main()
