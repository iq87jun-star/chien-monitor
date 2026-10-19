# -*- coding: utf-8 -*-
"""
median3_calibrate_compare.py — 土俵上の4構成(M3/M3+G3/R3a+G3/R4+G3)を
【中央値3ヶ月でFN P1(+8%)通過】になるよう倍率を逆算し、失格率込みで比較する。

先行(docs/63/75/76)との違い: 月次MCでなく【日次解像度】のブロックMC(月単位ブートストラップで
月内の日次構造=2024/8/5型の単日を保存)。失格は2つのバウンドで正直に挟む:
  - 楽観バウンド: EA日次ガード(-4%)が毎回完全執行 → 失格=月内トラフがフロア-8%到達(EA恒久停止)
  - 悲観バウンド: ガード執行なしの素の日次 → 失格=単日-5%(FN日次)超過 or トラフ-8%
  実際の失格率はこの間に落ちる(ギャップ/スリッページ次第)。
判定順序: 同月内でpassとfailが両方成立する場合はfail優先(保守側)。36ヶ月で未決着は別掲。
出力: results/median3_calibrate_compare.json → docs/111
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                     composite_daily, M3, YEN, V7X, EMON, EMONX)
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS

TARGET, FLOOR_OPT, DAY_FN, FLOOR_RAW = 0.08, -0.08, -0.05, -0.08
N_SEARCH, N_FINAL, MAXM = 4000, 20000, 36
SEED = 7


def month_arrays(daily):
    """月ごとの日次リターン配列"""
    mk = pd.PeriodIndex(daily.index, freq="M")
    return [np.asarray(daily[mk == m].values, float) for m in mk.unique()]


def month_stats_at(arrs, mult, g3_arrs=None):
    """倍率multでの月別: (楽観)実効月リターン/トラフ/ピーク, (素)最悪単日/トラフ"""
    out = []
    for i, a in enumerate(arrs):
        d = a * mult
        if g3_arrs is not None:
            d = d + g3_arrs[i]
        # 楽観: 単日を-4%でキャップ(ガード完全執行)
        dc = np.maximum(d, -0.04)
        eq = np.cumprod(1 + dc)
        out.append(dict(ret=eq[-1] - 1, trough=eq.min() - 1, peak=eq.max() - 1,
                        raw_min_day=d.min(),
                        raw_trough=np.cumprod(1 + d).min() - 1))
    return out


def simulate(ms, n_paths, rng):
    """→ (中央通過月[通過パスのみ], 通過%, 失格%楽観, 失格%悲観, 未決着%)"""
    n = len(ms)
    pass_m, fail_o, fail_r, undone = [], 0, 0, 0
    for _ in range(n_paths):
        e = 1.0; failed_o = False; failed_r = False; done = False
        for t in range(1, MAXM + 1):
            s = ms[rng.integers(0, n)]
            if not failed_r and (s["raw_min_day"] <= DAY_FN or e * (1 + s["raw_trough"]) <= 1 + FLOOR_RAW):
                failed_r = True
            if e * (1 + s["trough"]) <= 1 + FLOOR_OPT:
                failed_o = True; done = True     # fail優先(保守)
            elif e * (1 + s["peak"]) >= 1 + TARGET:
                pass_m.append(t); done = True
            e *= (1 + s["ret"])
            if done:
                break
        if failed_o:
            fail_o += 1
        if failed_r:
            fail_r += 1
        if not done:
            undone += 1
    med = float(np.median(pass_m)) if pass_m else np.nan
    return dict(median_months=med,
                pass_pct=round(100 * len(pass_m) / n_paths, 1),
                fail_pct_optimistic=round(100 * fail_o / n_paths, 1),
                fail_pct_raw=round(100 * fail_r / n_paths, 1),
                undone_pct=round(100 * undone / n_paths, 1))


def calibrate_median3(arrs, g3_arrs, rng):
    """中央値3ヶ月に最も近い倍率を粗→細で探索"""
    best, best_m = None, None
    for mult in np.arange(0.4, 4.01, 0.2):
        st = simulate(month_stats_at(arrs, mult, g3_arrs), N_SEARCH, rng)
        if not np.isnan(st["median_months"]) and st["median_months"] <= 3.0:
            best_m = mult; break
    if best_m is None:
        return None, None
    for mult in np.arange(max(0.4, best_m - 0.2), best_m + 0.201, 0.05):
        st = simulate(month_stats_at(arrs, mult, g3_arrs), N_SEARCH, rng)
        d = abs((st["median_months"] or 99) - 3.0)
        if best is None or d < best[0] or (d == best[0] and mult < best[1]):
            best = (d, mult)
    return round(best[1], 2), None


def main():
    rng = np.random.default_rng(SEED)
    print("[1/3] 日次スリーブ構築(portfolio_daily_compare流用)")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    g3 = g3_daily()

    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    RMAP = {r: {m: weights_for(r, mu.loc[m], sd.loc[m]) for m in range(1, 13)} for r in ("R3a", "R4")}

    variants = [("M3(現行)", M3, False), ("M3+G3", M3, True),
                ("R3a+G3", RMAP["R3a"], True), ("R4+G3", RMAP["R4"], True)]
    out = {}
    print("[2/3] 中央値3ヶ月への倍率校正(粗4000パス)→ [3/3] 本計測(20000パス)")
    for name, wmap, useG3 in variants:
        base = composite_daily(sleeves, wmap)
        arrs = month_arrays(base)
        g3a = None
        if useG3:
            g3s = g3.reindex(base.index).fillna(0.0)
            mk = pd.PeriodIndex(base.index, freq="M")
            g3a = [np.asarray(g3s[mk == m].values, float) for m in mk.unique()]
        mult, _ = calibrate_median3(arrs, g3a, rng)
        if mult is None:
            out[name] = dict(note="中央3ヶ月に到達する倍率が範囲(≤4x)に無い")
            continue
        st = simulate(month_stats_at(arrs, mult, g3a), N_FINAL, rng)
        # 参考: 月次成績(校正倍率で)
        s = base * mult
        if useG3:
            s = s.add(g3, fill_value=0.0)
        mk = pd.PeriodIndex(s.index, freq="M")
        mret = pd.Series({m: float((1 + s[mk == m]).prod() - 1) for m in mk.unique()})
        st.update(mult=mult, mean_month_pct=round(float(mret.mean() * 100), 2),
                  worst_month_pct=round(float(mret.min() * 100), 2),
                  worst_day_pct=round(float(s.min() * 100), 2))
        out[name] = st
        print(f"  {name:10s} {st}")

    res = dict(method="日次ブロックMC(月単位BS・36ヶ月上限)。楽観=日次-4%ガード完全執行/悲観=素の日次。"
                      "同月pass&failはfail優先。FN P1 +8%/フロア-8%(EA)/日次-5%(FN)",
               n_paths=N_FINAL, variants=out,
               reference="PortfolioD median-3標準(Drive確定・月次MC): 中央3ヶ月/失格4.9%(docs/76)")
    path = os.path.join(HERE, "results", "median3_calibrate_compare.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
