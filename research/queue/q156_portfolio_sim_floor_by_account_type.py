# -*- coding: utf-8 -*-
"""docs/399 Q156(診断・セル 0): portfolio_sim の資金化後の床・出金を口座型別(static / ftmo2step / ftmo1step / fn_instant)にした影響。
(1) 現行 config を旧モデル(全口座 静的床・分配 0.8)と新モデルで比較(docs/349 §9c〜§9f の合計月収の更新値)。
(2) FTMO 1-Step 531466484 の資金化後倍率を現行 ×3.125/2.03 から下げた格子で、資金化後の失格(到達者比)と月収の膝を探す(規約床 = EOD トレーリング・全額 Reward・分配 0.9)。
使い方: cd research && python3 -W ignore queue/q156_portfolio_sim_floor_by_account_type.py → results/q156_model_compare.csv・results/q156_onestep_sweep.csv"""
import os, sys, json, copy
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from forward.portfolio_sim import run_portfolio, summarize
N, SEED = 6000, 44
def table(res, lab):
    rows = []
    for nm, (jpy, pct) in res["per"].items():
        st = res["stats"][nm]; rows.append(dict(model=lab, account=nm, rule=st["rule"], share=st["share"], pay_mean_man=jpy.mean() / 1e4, pay_med_man=float(np.median(jpy)) / 1e4, pay_p16_man=float(np.quantile(jpy, .16)) / 1e4,
                                                  zero=(jpy <= 0).mean() * 100, reach=st["reach"] * 100, fail=st["fail"] * 100, fail_eval=st["fail_eval"] * 100, fail_funded=st["fail_funded"] * 100, fail_funded_of_reached=st["fail_funded_of_reached"] * 100))
    return rows
def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8"))
    rows = []; heads = []
    for lab, kw in [("legacy", dict(legacy=True)), ("by_rule", dict())]:
        res = run_portfolio(cfg, N=N, seed=SEED, **kw); s = summarize(res, lab); heads.append(s); rows += table(res, lab)
        print(f"{lab:<8} 合計: 期待 {s['mean']:.0f} 万 | −2σ {s['p023']:.0f} | −1σ {s['p16']:.0f} | 中央 {s['p50']:.0f} | +1σ {s['p84']:.0f} | 0 の確率 {s['p0']*100:.0f}%")
    D = pd.DataFrame(rows); D.to_csv(os.path.join(ROOT, "results", "q156_model_compare.csv"), index=False)
    pd.set_option("display.width", 250); print(D.round(1).to_string(index=False))
    # (2) 1-Step 資金化後倍率の格子
    sw = []
    for sc in (1.0, 0.8, 0.64, 0.48, 0.4, 0.32, 0.24):
        c = copy.deepcopy(cfg)
        for a in c["accounts"]:
            if a["name"].startswith("1-Step"): a["funded"] = {k: round(v * sc, 3) for k, v in a["funded"].items()}; spec = a["funded"]
        res = run_portfolio(c, N=N, seed=SEED); s = summarize(res, f"x{sc}"); jpy, pct = res["per"]["1-Step 531466484"]; st = res["stats"]["1-Step 531466484"]
        sw.append(dict(scale=sc, funded=json.dumps(spec), total_mean=s["mean"], total_p16=s["p16"], total_p50=s["p50"], onestep_mean_man=jpy.mean() / 1e4, onestep_med_man=float(np.median(jpy)) / 1e4, onestep_zero=(jpy <= 0).mean() * 100,
                       reach=st["reach"] * 100, fail_funded_of_reached=st["fail_funded_of_reached"] * 100))
        print(f"1-Step 資金化後 ×{sc:<4} {spec} | 1-Step 期待 {jpy.mean()/1e4:5.1f} 万/月 中央 {np.median(jpy)/1e4:5.1f} 0率 {(jpy<=0).mean()*100:3.0f}% | 資金化後失格(到達者比) {st['fail_funded_of_reached']*100:5.1f}% | 全体 期待 {s['mean']:.0f} −1σ {s['p16']:.0f} 中央 {s['p50']:.0f}")
    pd.DataFrame(sw).to_csv(os.path.join(ROOT, "results", "q156_onestep_sweep.csv"), index=False); print("saved results/q156_model_compare.csv, q156_onestep_sweep.csv")
if __name__ == "__main__": main()
