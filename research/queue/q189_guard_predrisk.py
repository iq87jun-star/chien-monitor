# -*- coding: utf-8 -*-
"""docs/244 Q189(診断・セル 0・2026-11-13 登録「登録して実行」): 全決済ガード g の手前(当日の確定 + 含み損益 ≤ −θ×g)で建玉を半分決済し、
その日の残りの新規も半分にする規則を、日次ガード込みの口座モデル(Q187・docs/428)で現行と比べる。θ ∈ {0.4, 0.5, 0.6, 0.75}。
近似: 半減の時刻 j1 より後は、ガード指標・合計損益の増減を 0.5 倍(j1 が月曜で以後が火曜なら指標 = 0.5 × 元の指標)。その後 −g に達すれば全決済。
半減は月内 2 回の停止に数えない・滑りなし。共有関数は q188_skew_gate_guard_model.py。
使い方: cd research && python3 -W ignore queue/q189_guard_predrisk.py   出力: results/q189_guard_predrisk.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, paths, run_guard, evaluate, account_items, verdict = (ns[k] for k in ("cfg", "paths", "run_guard", "evaluate", "account_items", "verdict"))
THETAS = [0.4, 0.5, 0.6, 0.75]; rows = []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if not items: continue
    P = paths(items, cap); ex = dict(guard_pct=round(g * 100, 1), mondays=len(P))
    rows += evaluate(a, aid, run_guard(P, g), "現行", ex)
    for th in THETAS: rows += evaluate(a, aid, run_guard(P, g, th), f"θ={th}", dict(ex, derisk_at_pct=round(th * g * 100, 2)))
D = pd.DataFrame(rows); D.to_csv("results/q189_guard_predrisk.csv", index=False); picks = []
for (acct, sc), g_ in D[D.scen != "—"].groupby(["acct", "scen"], sort=False):
    cur, best = verdict(g_, "現行")
    picks.append(dict(acct=acct, scen=sc, cur_reach_lo=cur.reach_lo, cur_reach_cl=cur.reach_cl, cur_fail_lo=cur.fail_lo, cur_weeks=cur.weeks_lo, cur_hits_lo=cur.hits_lo, cur_mean_lo=cur.mean_bps_lo,
                      verdict=("変更候補" if best is not None else "現行維持"), variant=(best.variant if best is not None else "現行"), reach_lo=(best.reach_lo if best is not None else None), reach_cl=(best.reach_cl if best is not None else None),
                      fail_lo=(best.fail_lo if best is not None else None), weeks=(best.weeks_lo if best is not None else None), hits_lo=(best.hits_lo if best is not None else None), mean_lo=(best.mean_bps_lo if best is not None else None)))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q189_guard_predrisk_pick.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print(Pk.to_string(index=False)); print()
cols = ["acct", "scen", "variant", "mean_bps_lo", "hits_lo", "derisk_lo", "mean_bps_cl", "hits_cl", "derisk_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo", "reach8w_lo"]
print(D[[c for c in cols if c in D.columns]].to_string(index=False))
