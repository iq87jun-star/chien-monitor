# -*- coding: utf-8 -*-
"""
portfolio_all_median3.py — 現行・準備済みの全ポートフォリオを中央3ヶ月で同土俵比較。
方法: median3_calibrate_compare(docs/111)の機械を逐語再利用(日次ブロックMC・FN P1+8%・
シード7・2万パス・fail優先・楽観/悲観2バウンド)。窓2016-01〜2026-06・Yahoo日足。
対象: 季節R4+G3 / PD現行 / PD間引き(docs/135) / PortfolioE v2=E5p単独(docs/133) / PE v1(参考)。
出力: results/portfolio_all_median3.json → docs/139
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


def mstats(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()
    sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    return dict(mean_month=round(float(m.mean() * 100), 2), sharpe=round(sh, 2),
                worst_month=round(float(m.min() * 100), 2), worst_day=round(float(s.min() * 100), 2))


def run_variant(name, base, g3=None):
    arrs = month_arrays(base)
    g3a = None
    if g3 is not None:
        g3s = g3.reindex(base.index).fillna(0.0)
        mk = pd.PeriodIndex(base.index, freq="M")
        g3a = [np.asarray(g3s[mk == m].values, float) for m in mk.unique()]
    mult, _ = calibrate_median3(arrs, g3a, np.random.default_rng(SEED))
    if mult is None:
        print(f"  {name}: 中央3ヶ月に到達不可(≤4x)")
        return dict(note="中央3ヶ月に到達不可(≤4x)")
    st = simulate(month_stats_at(arrs, mult, g3a), N_FINAL, np.random.default_rng(SEED))
    s = base * mult
    if g3 is not None:
        s = s.add(g3, fill_value=0.0)
    rec = dict(mult=mult, **st, **mstats(s))
    print(f"  {name}: mult={mult} {st} {mstats(s)}")
    return rec


def main():
    print("[1/2] スリーブ構築")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    v7p = mon_daily(["EURJPY", "GBPJPY"])
    e5p = e5_basket(["XAUUSD", "NAS100"])
    g3 = g3_daily()

    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}

    PD = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    sleeves_p = dict(sleeves); sleeves_p["v7"] = v7p; sleeves_p["E5"] = e5p

    print("[2/2] 校正+MC(各2万パス)")
    out = {}
    out["季節R4+G3(稼働中)"] = run_variant("季節R4+G3", composite_daily(sleeves, R4), g3)
    out["PD現行(稼働中)"] = run_variant("PD現行", composite_daily(sleeves, PD))
    out["PD間引き(次チャレンジ用)"] = run_variant("PD間引き", composite_daily(sleeves_p, PD))
    out["PortfolioE_v2(E5p単独)"] = run_variant("PE v2", e5p)
    out["参考:PortfolioE_v1(E5 4資産)"] = run_variant("PE v1", e5_daily())

    res = dict(meta=dict(method="docs/111と同一(日次ブロックMC・FN P1+8%・シード7・2万パス)",
                         window="2016-01..2026-06", inputs=sha256s(),
                         caveat="Yahoo日足=絶対値は保守側(docs/111 §3)。v4含む構成はYahooで過小評価"
                                "(docs/138)=季節/PD行は実データでより良い側。相対比較が主眼"),
               variants=out)
    path = os.path.join(HERE, "results", "portfolio_all_median3.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
