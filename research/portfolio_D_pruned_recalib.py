# -*- coding: utf-8 -*-
"""
portfolio_D_pruned_recalib.py — PD間引き版(v7 2クロス+E5 2資産)の中央3ヶ月再校正【事前登録 docs/134 §2】。
現行PD(v4 30/v7 25/E-Mon 25/E5 20)と間引きPDを median3_calibrate_compare の日次ブロックMCで
同じ土俵で校正・比較。決定規則: 間引き版の失格%(楽観・悲観とも)が現行以下なら採用。
出力: results/portfolio_D_pruned_recalib.json → docs/135
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import mon_daily, e5_daily, v4_daily, composite_daily, YEN, EMON
from policy_prune_symbols import e5_basket
import median3_calibrate_compare as m3c
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from seasonal_optimize_loyo import sha256s

PD_W = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
SEED, N_FINAL = 7, 20000


def monthly_stats_simple(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()
    return dict(mean_month=round(float(m.mean() * 100), 2), worst_month=round(float(m.min() * 100), 2),
                worst_day=round(float(s.min() * 100), 2))


def run_variant(name, sleeves):
    base = composite_daily(sleeves, PD_W)
    arrs = month_arrays(base)
    rng = np.random.default_rng(SEED)
    mult, _ = calibrate_median3(arrs, None, rng)
    if mult is None:
        return dict(note="中央3ヶ月に到達する倍率なし")
    st = simulate(month_stats_at(arrs, mult, None), N_FINAL, np.random.default_rng(SEED))
    out = dict(mult=mult, **st, **monthly_stats_simple(base * mult))
    print(f"  {name}: mult={mult} {st}")
    return out


def main():
    print("[1/2] スリーブ構築")
    v4 = v4_daily()
    emon = mon_daily(EMON, 3e-4)
    cur = dict(v4=v4, v7=mon_daily(YEN), EMon=emon, E5=e5_daily())
    prn = dict(v4=v4, v7=mon_daily(["EURJPY", "GBPJPY"]), EMon=emon,
               E5=e5_basket(["XAUUSD", "NAS100"]))

    print("[2/2] 中央3ヶ月校正+MC(2万パス)")
    r_cur = run_variant("PD現行", cur)
    r_prn = run_variant("PD間引き", prn)

    adopt = (r_prn.get("fail_pct_optimistic", 99) <= r_cur.get("fail_pct_optimistic", 0) and
             r_prn.get("fail_pct_raw", 99) <= r_cur.get("fail_pct_raw", 0))
    ratio = round(r_prn["mult"] / r_cur["mult"], 3) if adopt else None
    ea = None
    if adopt:
        ea = dict(InpYenSymbols="EURJPY,GBPJPY", InpV7ShotsPerWeek=8,
                  InpE5Symbols="XAUUSD,NAS100",
                  InpWeeklyRiskPct=round(1.95 * ratio, 2),
                  InpV4RiskPerTradePct=round(0.58 * ratio, 2),
                  InpEMonWeeklyPct=round(1.95 * ratio, 2),
                  InpE5LegRiskPct=round(1.56 * 2 * ratio, 2),
                  note="標準(docs/76)×倍率比。E5は2レッグ化補償で×2(docs/133 §3)")
    res = dict(meta=dict(prereg="docs/134 §2", seed=SEED, n_paths=N_FINAL, inputs=sha256s()),
               PD_current=r_cur, PD_pruned=r_prn,
               decision=dict(adopt=bool(adopt), mult_ratio=ratio, ea_inputs=ea,
                             rule="間引き版の失格%(楽観・悲観)がともに現行以下なら採用"))
    path = os.path.join(HERE, "results", "portfolio_D_pruned_recalib.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"採用={adopt} ratio={ratio}")
    if ea: print("EA入力:", ea)
    print("保存:", path)


if __name__ == "__main__":
    main()
