# -*- coding: utf-8 -*-
"""
fn_realloc_calib.py — FN再配置(docs/161 §4対応)の校正。
  A) FN200k P1: PD間引き【E5抜き】(v4/v7p/EMon = 37.5/31.25/31.25に再正規化)の中央3ヶ月校正
     (参考: E5込みPD間引き=docs/135の再現)
  B) FN100k P1: PE v2(E5p単独)の中央3ヶ月校正+固定倍率0.675x(std)/1.0x(x15)の通過統計
方法: median3_calibrate_compare(docs/111)を逐語流用(FN P1 +8%/フロア-8%/日次-5%・シード7・2万パス)。
出力: results/fn_realloc_calib.json → docs/163
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
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from portfolio_all_median3 import mstats

SEED, N_FINAL = 7, 20000


def run_at(base, mult, rng):
    st = simulate(month_stats_at(month_arrays(base), mult), N_FINAL, rng)
    return dict(mult=mult, **st, **mstats(base * mult))


def calib(base, rng):
    mult, _ = calibrate_median3(month_arrays(base), None, rng)
    if mult is None:
        return dict(note="中央3ヶ月に到達不可(≤4x)")
    return run_at(base, mult, rng)


def main():
    print("[1/3] スリーブ構築")
    sleeves = dict(v7=mon_daily(["EURJPY", "GBPJPY"]), EMon=mon_daily(EMON, 3e-4),
                   E5=e5_basket(["XAUUSD", "NAS100"]), v4=v4_daily(),
                   v7x=mon_daily(V7X), EMonX=mon_daily(EMONX, 3e-4),
                   SJul=cc_daily(["US500", "NAS100"]))
    PD_FULL = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    PD_NOE5 = {m: {"v4": .375, "v7": .3125, "EMon": .3125} for m in range(1, 13)}

    out = {}
    print("[2/3] 校正")
    base_noe5 = composite_daily(sleeves, PD_NOE5)
    out["PD間引きE5抜き(200k用)"] = calib(base_noe5, np.random.default_rng(SEED))
    print("  PD-noE5:", out["PD間引きE5抜き(200k用)"])
    base_full = composite_daily(sleeves, PD_FULL)
    out["参考:PD間引きE5込み(docs/135)"] = calib(base_full, np.random.default_rng(SEED))
    print("  PD-full:", out["参考:PD間引きE5込み(docs/135)"])

    e5p = sleeves["E5"]
    out["PE_v2校正(中央3ヶ月)"] = calib(e5p, np.random.default_rng(SEED))
    print("  PEv2 med3:", out["PE_v2校正(中央3ヶ月)"])
    for m, tag in [(0.675, "PE_v2@std(legRisk1.35)"), (1.0, "PE_v2@x15(legRisk2.00)")]:
        out[tag] = run_at(e5p, m, np.random.default_rng(SEED))
        print(f"  {tag}:", out[tag])

    res = dict(meta=dict(method="docs/111と同一(日次ブロックMC・FN P1+8%・シード7・2万パス)",
                         window="2016-01..2026-06", inputs=sha256s(),
                         caveat="Yahoo=v4含む構成は過小側(docs/138)。PD行は実運用でより良い側。"),
               variants=out)
    path = os.path.join(HERE, "results", "fn_realloc_calib.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("[3/3] 保存:", path)


if __name__ == "__main__":
    main()
