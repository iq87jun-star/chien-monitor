# -*- coding: utf-8 -*-
"""
instant20k_alt_vehicles_mc.py — FN Instant $20k(トレーリング−6%建値ロック)での代替戦略校正。
背景: FN書面回答(docs/161 §4)によりInstant×季節は不可(チャレンジ口座と同一取引になるため)。
Instant候補 = PD間引き(docs/135) / PortfolioE v2=E5p単独(docs/133)。
方法: instant50k_seasonal_trailing_mc.py(失格MC)+instant20k_stepup_mc.py(昇格レース)を逐語流用。
出力: results/instant20k_alt_vehicles.json → docs/162
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily,
                                     composite_daily, YEN, V7X, EMON, EMONX)
from policy_prune_symbols import e5_basket
from seasonal_optimize_loyo import sha256s
from instant50k_seasonal_trailing_mc import month_paths, simulate_trailing, mstats
from instant20k_stepup_mc import simulate_stepup

SEED, N_PATHS, HORIZON = 7, 20000, 36
MULTS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def main():
    print("[1/3] スリーブ構築(portfolio_all_median3と同一)")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    v7p = mon_daily(["EURJPY", "GBPJPY"])
    e5p = e5_basket(["XAUUSD", "NAS100"])
    PD = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    sleeves_p = dict(sleeves); sleeves_p["v7"] = v7p; sleeves_p["E5"] = e5p
    bases = {"PD間引き": composite_daily(sleeves_p, PD), "PE_v2(E5p単独)": e5p}

    print("[2/3] 倍率別: トレーリング−6%(lock)失格MC + 昇格(+10%)レース(各2万パス)")
    out = {}
    for name, base in bases.items():
        rec = {}
        for mult in MULTS:
            months = month_paths(base * mult)
            tr = simulate_trailing(months, 0.06, True, N_PATHS, HORIZON,
                                   np.random.default_rng(SEED))
            su = simulate_stepup(months, N_PATHS, HORIZON, np.random.default_rng(SEED))
            rec[f"x{mult}"] = dict(monthly=mstats(base * mult),
                                   trailing_lock=tr, stepup=su)
            print(f"  {name} x{mult}: 失格12m={tr['breach_pct_12m']}% "
                  f"昇格中央={su['median_stepup_month']}ヶ月 成功={su['stepup_pct']}% "
                  f"12m内昇格={su['stepup_within_12m_pct']}%")
        out[name] = rec

    res = dict(meta=dict(
        method="docs/154(トレーリングlock)+docs/155(昇格レース)の機械を逐語流用。"
               "同月内昇格/失格は日次先着・同日fail優先。中間出金なし想定。",
        rule="FN Stellar Instant −6%建値ロック(docs/161 §1で公式確認)",
        window="2016-01..2026-06", n_paths=N_PATHS, horizon_months=HORIZON,
        inputs=sha256s(),
        caveat="Yahoo日足=v4含む構成(PD)は実データ比で過小側(docs/138)。"
               "季節との比較はdocs/154/155の同条件の値を参照。"),
        variants=out)
    path = os.path.join(HERE, "results", "instant20k_alt_vehicles.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("[3/3] 保存:", path)


if __name__ == "__main__":
    main()
