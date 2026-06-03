#!/usr/bin/env python3
"""E3 再評価（事後ロバストネス確認 / docs/27 の判定は変えない）。

事前登録の E3 は Yahoo 金先物(GC=F)・日足プロキシ相関で REJECT 確定。
本スクリプトは出典を **Dukascopy 金スポット(XAUUSD)実 H1→日足** に替え、
**金スプレッドを実測値**で計上し、**v7 相関を精密(実 H1)版**で再算出して、
判定が出典に頑健か（＝ REJECT が偶然でないか）を確認する。

※これは事後分析。ADOPT を作り直す行為ではない（規律: 当たるまで条件を変えない）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0125
VIX_QUANTILE = 0.80
ROLL = 252


def _read_gold_spread_frac(default=0.00015):
    """XAUUSD_spread.txt（実測中央値・片道 frac）。無ければ控えめ既定。"""
    p = os.path.join(data.data_dir(), "XAUUSD_spread.txt")
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("median_frac="):
                return float(line.split("=")[1])
    return default


def build(cost_frac):
    vix = data.load_daily("VIX")["close"].astype(float)
    thr = vix.rolling(ROLL).quantile(VIX_QUANTILE)
    entries = vix.index[(vix > thr).fillna(False)] + __import__("pandas").Timedelta(days=1)
    xau = data.load_daily("XAUUSD")
    return engine.daily_R(engine.event_trades_daily(xau, entries, +1, 1, cost_frac=cost_frac))


def main():
    import pandas as pd
    spread_frac = _read_gold_spread_frac()
    print(f"[info] 金スプレッド(実測・片道frac)= {spread_frac:.6f} = {spread_frac*1e4:.2f}bp")

    d_gross = build(cost_frac=0.00005)        # ほぼコストなし(グロス)
    d_real = build(cost_frac=spread_frac)     # 実測スプレッド計上

    # プラセボ(低ボラ・レジーム)
    vix = data.load_daily("VIX")["close"].astype(float)
    lo = vix.rolling(ROLL).quantile(0.20)
    lo_entries = vix.index[(vix < lo).fillna(False)] + pd.Timedelta(days=1)
    xau = data.load_daily("XAUUSD")
    placebo = {"low_vol_regime": engine.daily_R(engine.event_trades_daily(xau, lo_entries, +1, 1)).values}

    # v7 相関（実 H1 があれば精密版が自動採用される）
    v7w, src = v7_reference.v7_weekly_R_auto()
    v7_corr = v7_reference.corr_with_v7(d_gross)
    print(f"[info] v7 相関ソース = {src}  (H1=精密 / daily_proxy=近似)")

    res = evaluate.evaluate(
        "E3_REVALIDATE_dukascopy_spot", ALPHA, d_gross.values, d_gross.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_real.values,
    )
    res["data_source"] = "Dukascopy XAUUSD spot H1->daily"
    res["gold_spread_frac"] = spread_frac
    res["v7_corr_source"] = src
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d_gross, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge3_revalidate_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
