# -*- coding: utf-8 -*-
"""
seasonal_pruned_median3.py — 季節R4+G3に間引き(v7 2クロス/E5 2資産)を適用した場合の同土俵比較。
方法: docs/111/139と同一(日次ブロックMC・FN P1+8%・シード7・2万パス・中央3ヶ月校正)。
変種: 現行R4+G3 / A=月別テーブル据置+スリーブ間引き / B=間引き統計で重み再導出+間引き。
採用規則(docs/135と同型): 失格%(楽観・悲観とも)が現行以下の変種のみ採用候補(デモ必須)。
出力: results/seasonal_pruned_median3.json → docs/140
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                     composite_daily, YEN, V7X, EMON, EMONX)
from policy_prune_symbols import e5_basket
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS, sha256s

SEED, N_FINAL = 7, 20000


def to_monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()


def mstats(s):
    m = to_monthly(s)
    sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    return dict(mean_month=round(float(m.mean() * 100), 2), sharpe=round(sh, 2),
                worst_month=round(float(m.min() * 100), 2), worst_day=round(float(s.min() * 100), 2))


def run_variant(name, base, g3):
    arrs = month_arrays(base)
    g3s = g3.reindex(base.index).fillna(0.0)
    mk = pd.PeriodIndex(base.index, freq="M")
    g3a = [np.asarray(g3s[mk == m].values, float) for m in mk.unique()]
    mult, _ = calibrate_median3(arrs, g3a, np.random.default_rng(SEED))
    if mult is None:
        print(f"  {name}: 校正不可"); return dict(note="校正不可")
    st = simulate(month_stats_at(arrs, mult, g3a), N_FINAL, np.random.default_rng(SEED))
    s = base * mult
    s = s.add(g3, fill_value=0.0)
    rec = dict(mult=mult, **st, **mstats(s))
    print(f"  {name}: mult={mult} {st} {mstats(s)}")
    return rec


def main():
    print("[1/3] スリーブ構築")
    sl_cur = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                  EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                  E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    sl_prn = dict(sl_cur)
    sl_prn["v7"] = mon_daily(["EURJPY", "GBPJPY"])
    sl_prn["E5"] = e5_basket(["XAUUSD", "NAS100"])
    g3 = g3_daily()

    print("[2/3] R4重みテーブル")
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}

    # B: v7/E5列を間引き版の月次に差し替えて再導出(他スリーブは既存dfmのまま)
    dfm_p = dfm.copy()
    for col, s in [("v7", sl_prn["v7"]), ("E5", sl_prn["E5"])]:
        mm = to_monthly(s)                       # PeriodIndex(M) = build_sleevesと同じ
        dfm_p[col] = mm.reindex(dfm_p.index).values
    mu_p, sd_p = month_stats(dfm_p.fillna(0.0), LOYO_YEARS)
    R4p = {m: weights_for("R4", mu_p.loc[m], sd_p.loc[m]) for m in range(1, 13)}

    print("[3/3] 校正+MC")
    out = {}
    out["現行R4+G3"] = run_variant("現行", composite_daily(sl_cur, R4), g3)
    out["A_テーブル据置+間引き"] = run_variant("A", composite_daily(sl_prn, R4), g3)
    out["B_重み再導出+間引き"] = run_variant("B", composite_daily(sl_prn, R4p), g3)
    out["B_月別重み(参考)"] = {m: {k: round(v, 3) for k, v in R4p[m].items()} for m in range(1, 13)}

    b = out["現行R4+G3"]
    cands = [k for k in ("A_テーブル据置+間引き", "B_重み再導出+間引き")
             if "mult" in out[k]
             and out[k]["fail_pct_optimistic"] <= b["fail_pct_optimistic"]
             and out[k]["fail_pct_raw"] <= b["fail_pct_raw"]]
    verdict = (f"採用候補: {min(cands, key=lambda k: out[k]['fail_pct_optimistic'])}(デモ必須)"
               if cands else "現行維持(間引き適用で改善なし)")
    res = dict(meta=dict(method="docs/111/139と同一", window="2016-01..2026-06", seed=SEED,
                         n_paths=N_FINAL, inputs=sha256s(),
                         note="v4は両変種に同一に含まれるためYahooバイアスは相対比較でほぼ相殺"),
               variants={k: v for k, v in out.items() if k != "B_月別重み(参考)"},
               R4p_weights=out["B_月別重み(参考)"], verdict=verdict)
    path = os.path.join(HERE, "results", "seasonal_pruned_median3.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("判定:", verdict)
    print("保存:", path)


if __name__ == "__main__":
    main()
