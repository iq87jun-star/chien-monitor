# -*- coding: utf-8 -*-
"""
instant50k_seasonal_trailing_mc.py — 季節R4+G3を【インスタント口座のトレーリングDD】で計測。
ユーザー質問(2026-07-15)「インスタント50kを季節eaで考えてます。どの様な成績になりますか」への回答用。

方法: docs/111系の日次ブロックMC(月単位ブートストラップ=月内の日次構造を保存)を逐語流用し、
失格条件だけをインスタント用トレーリングDDに置換する。
  - ルール: フロア = HWM(equity日次最高値) − X×初期残高。
      X=6%(FN Stellar Instant型) / X=10%(Blueberry Instant Elite型)
  - 各Xで2変種を正直に併記(実際はこの間・要規約確認):
      lock  = フロアが初期残高に達したら固定(建値ロック型・寛大側)
      pure  = フロアが無限に切り上がる(純トレーリング・厳格側)
  - 日次closeベース(ザラ場内のトラフは捉えない=失格は実際にはこれよりやや高い)。
  - 日次ガードのキャップは掛けない(素の日次=保守側。FN Instantに日次ルールなし, docs/97)。
構成: 季節R4+G3(portfolio_all_median3.pyと同一構築)。倍率グリッド 0.5/0.75/1.0/1.25/1.5。
出力: results/instant50k_seasonal_trailing.json → docs/154
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                     composite_daily, YEN, V7X, EMON, EMONX)
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS, sha256s

SEED, N_PATHS, HORIZON = 7, 20000, 36
MULTS = [0.5, 0.75, 1.0, 1.25, 1.5]
RULES = [("FN_Instant_6pct", 0.06), ("Blueberry_10pct", 0.10)]


def month_paths(daily):
    """月ごとの (日次equity累積, その累積の走り最大) を前計算"""
    mk = pd.PeriodIndex(daily.index, freq="M")
    out = []
    for m in mk.unique():
        a = np.asarray(daily[mk == m].values, float)
        cp = np.cumprod(1.0 + a)
        out.append((cp, np.maximum.accumulate(cp)))
    return out


def simulate_trailing(months, X, lock, n_paths, horizon, rng):
    """トレーリングDDのMC。equityは初期残高=1.0の倍数。
    フロア = hwm − X (lockならmin(・, 1.0)で頭打ち)。equity(日次close) <= フロア で失格。"""
    nm = len(months)
    e = np.ones(n_paths)
    hwm = np.ones(n_paths)
    alive = np.ones(n_paths, dtype=bool)
    breach_month = np.full(n_paths, -1)
    eq12 = np.full(n_paths, np.nan)
    for t in range(1, horizon + 1):
        idx = rng.integers(0, nm, size=n_paths)
        for m in np.unique(idx[alive]):
            sel = alive & (idx == m)
            if not sel.any():
                continue
            cp, cmx = months[m]
            eq = e[sel, None] * cp[None, :]                       # (k, days)
            hw = np.maximum(hwm[sel, None], e[sel, None] * cmx[None, :])
            floor = hw - X
            if lock:
                floor = np.minimum(floor, 1.0)
            br = (eq <= floor).any(axis=1)
            ii = np.where(sel)[0]
            breach_month[ii[br]] = t
            alive[ii[br]] = False
            ok = ii[~br]
            e[ok] = e[ok] * cp[-1]
            hwm[ok] = hw[~br, -1]
        if t == 12:
            eq12[alive] = e[alive]
    surv6 = float((~((breach_month > 0) & (breach_month <= 6))).mean())
    surv12 = float((~((breach_month > 0) & (breach_month <= 12))).mean())
    surv36 = float(alive.mean())
    bm = breach_month[breach_month > 0]
    a12 = eq12[~np.isnan(eq12)]
    return dict(
        breach_pct_6m=round(100 * (1 - surv6), 1),
        breach_pct_12m=round(100 * (1 - surv12), 1),
        breach_pct_36m=round(100 * (1 - surv36), 1),
        median_breach_month=(float(np.median(bm)) if bm.size else None),
        alive12_median_gain_pct=(round(float(np.median(a12) - 1) * 100, 1) if a12.size else None),
        alive12_p25_gain_pct=(round(float(np.percentile(a12, 25)) - 1, 4) * 100 if a12.size else None),
    )


def mstats(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()
    sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    return dict(mean_month_pct=round(float(m.mean() * 100), 2),
                median_month_pct=round(float(m.median() * 100), 2),
                worst_month_pct=round(float(m.min() * 100), 2),
                worst_day_pct=round(float(s.min() * 100), 2),
                pos_month_pct=round(float((m > 0).mean() * 100), 1),
                ann_sharpe=round(sh, 2),
                ann_return_pct=round(float(((1 + m.mean()) ** 12 - 1) * 100), 1))


def main():
    print("[1/3] スリーブ構築(portfolio_all_median3と同一)")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    g3 = g3_daily()
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    base = composite_daily(sleeves, R4)
    g3s = g3.reindex(base.index).fillna(0.0)

    print("[2/3] 倍率×ルールのトレーリングMC(各2万パス・36ヶ月)")
    out = {}
    for mult in MULTS:
        s = base * mult + g3s
        months = month_paths(s)
        rec = dict(monthly=mstats(s))
        for rname, X in RULES:
            for lock in (True, False):
                key = f"{rname}_{'lock' if lock else 'pure'}"
                rec[key] = simulate_trailing(months, X, lock, N_PATHS, HORIZON,
                                             np.random.default_rng(SEED))
                print(f"  mult={mult} {key}: {rec[key]}")
        out[f"x{mult}"] = rec

    res = dict(meta=dict(
        method="日次ブロックMC(月単位BS・docs/111系流用)。失格=日次closeのequityがトレーリング"
               "フロア(HWM−X×初期)以下。lock=フロア建値で固定/pure=無限切上げの2変種で挟む。"
               "日次ガードキャップなし(素の日次=保守)。日次close解像度=実際の失格はやや高い側。",
        window="2016-01..2026-06", n_paths=N_PATHS, horizon_months=HORIZON,
        composition="季節R4+G3(WR4月別表・G3は倍率非適用=EA実装と同一)",
        inputs=sha256s(),
        caveat="Yahoo日足=v4含む構成は実データ比で過小評価側(docs/138)。絶対値は保守。"),
        variants=out)
    path = os.path.join(HERE, "results", "instant50k_seasonal_trailing.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("[3/3] 保存:", path)


if __name__ == "__main__":
    main()
