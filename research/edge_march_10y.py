"""
edge_march_10y.py — 第4弾（docs/33, LOCKED）日本3月期末レパトリ・フローの10年検定。

仮説: 3月最終10営業日に本邦回帰でJPY高 → USDJPY/EURJPY/GBPJPY をショート（JPYロング）・等加重。
評価: 年ブロック符号順列（自己相関頑健）/ 月特異性プラセボ / Deflated Sharpe / PBO。
検出力は年10サイクルと低い点を承知の上で正直に判定（docs/33 §1）。
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from data_io import load_h1, load_costs, load_v7_weekly, report_path
from validation import deflated_sharpe, pbo_cscv

PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
N_TRIALS = 60
ALPHA = 0.05


def daily_short_jpy_cross() -> pd.DataFrame:
    """各JPYクロスの日次「ショート」リターン（=JPYロング, コスト控除）。"""
    costs = load_costs()
    cols = {}
    for p in PAIRS:
        c = load_h1(p)["close"].resample("1D").last().dropna()
        rt = -(c.pct_change())                         # ショート = JPY高で利益
        cols[p] = rt
    df = pd.DataFrame(cols).dropna(how="all")
    rt = df.mean(axis=1)                               # 3クロス等加重
    cost = np.mean([costs.loc[p, "roundtrip_cost_frac"] for p in PAIRS]) if all(p in costs.index for p in PAIRS) else 0.0001
    return rt, cost


def window_mask(idx: pd.DatetimeIndex, month: int, last_n: int) -> pd.Series:
    """各年の指定月の最終 last_n 営業日(=データ存在日) に True。"""
    s = pd.Series(False, index=idx)
    for y in sorted(set(idx.year)):
        days = idx[(idx.year == y) & (idx.month == month)]
        if len(days) >= last_n:
            s.loc[days[-last_n:]] = True
        elif len(days) > 0:
            s.loc[days] = True
    return s


def yearly_window_returns(rt: pd.Series, month=3, last_n=10) -> pd.Series:
    """各年の window 合計リターン（年ブロック順列の単位）。"""
    m = window_mask(rt.index, month, last_n)
    sub = rt[m]
    return sub.groupby(sub.index.year).sum()


def year_block_sign_p(yearly: pd.Series, n_perm=20000, seed=7) -> float:
    x = yearly.values.astype(float); x = x[np.isfinite(x)]
    if len(x) == 0:
        return 1.0
    obs = x.mean()
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(x)))
    perm = (signs * x).mean(axis=1)
    return float((np.sum(perm >= obs) + 1) / (n_perm + 1))


def jackknife_year(yearly: pd.Series) -> float:
    ys = list(yearly.index)
    return max(year_block_sign_p(yearly.drop(y)) for y in ys) if len(ys) > 2 else 1.0


def main():
    rt, cost = daily_short_jpy_cross()
    rt_net = rt - 0.0  # コストは window 集計時に営業日数ぶん概算で引く
    LAST_N = 10

    # 本登録（3月）
    yr = yearly_window_returns(rt, 3, LAST_N)
    # コスト: window 中 1回転/日 ではなく、入口出口の往復1回として控除（保守的に営業日数で薄く）
    yr_net = yr - cost  # 年あたり往復1回ぶん
    net = float(yr_net.sum())
    p = year_block_sign_p(yr_net)
    jk = jackknife_year(yr_net)

    # ④ 月特異性プラセボ: 全12ヶ月の window 平均、3月が突出か
    month_means = {}
    for mth in range(1, 13):
        ym = yearly_window_returns(rt, mth, LAST_N) - cost
        month_means[mth] = float(ym.mean())
    march = month_means[3]
    others = np.mean([v for m, v in month_means.items() if m != 3])
    rank = sorted(month_means, key=month_means.get, reverse=True).index(3) + 1  # 1=最高
    g4 = bool(march > 0 and march > others and rank <= 2)

    # ⑥ v7独立性: 日次windowリターンを週次にして v7 と相関
    m = window_mask(rt.index, 3, LAST_N)
    wk = (rt[m]).resample("W-MON").sum()
    v7 = load_v7_weekly()
    a, b = wk.align(v7, join="inner")
    corr = float(np.corrcoef(a.values, b.values)[0, 1]) if len(a) >= 8 and a.std() > 0 else float("nan")

    # ⑦ DSR（年次系列で）/ ⑧ PBO（window長変種 × 年）
    dsr = deflated_sharpe(yr_net.values, n_trials=N_TRIALS, sr_trials_std=0.3)
    variants = []
    for ln in (8, 10, 12, 15):
        variants.append(yearly_window_returns(rt, 3, ln).values)
    L = min(len(v) for v in variants)
    M = np.column_stack([v[-L:] for v in variants])
    pbo = pbo_cscv(M, n_splits=min(10, L if L % 2 == 0 else L - 1)) if L >= 6 else {"pbo": float("nan")}

    gates = {
        "g1_profit": net > 0,
        "g2_perm_p": p < ALPHA,
        "g3_jackknife": jk <= 0.10,
        "g4_month_placebo": g4,
        "g5_cost": net > 0 and p < ALPHA,
        "g6_independent": (not np.isnan(corr)) and abs(corr) <= 0.30,
        "g7_dsr": dsr["dsr"] >= 0.95,
        "g8_pbo": np.isfinite(pbo["pbo"]) and pbo["pbo"] <= 0.20,
    }
    gates = {k: bool(v) for k, v in gates.items()}
    grade = "ADOPT" if all(gates.values()) else ("LEAD" if (net > 0 and p < 0.10) else "REJECT")
    out = {
        "edge_id": "March_repat", "period": "2016..2025", "alpha": ALPHA,
        "n_years": int(len(yr)), "net_10y": net, "perm_p_year": p, "jackknife_max_p": jk,
        "march_mean": march, "other_months_mean": others, "march_rank_of_12": rank,
        "corr_v7": corr, "dsr": dsr["dsr"], "sharpe_yearly": dsr["sharpe"],
        "pbo": pbo["pbo"], "gates": gates, "grade": grade,
        "month_means": month_means,
    }
    with open(report_path("march_repat_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("=== March repatriation 10-year verdict (N=1, alpha=0.05, N_trials=60) ===")
    print(f"grade={grade}  n_years={len(yr)}  net={net:+.4f}  perm_p={p:.4f}  jk_maxp={jk:.4f}")
    print(f"march_mean={march:+.5f}  other_months={others:+.5f}  march_rank={rank}/12")
    print(f"corr_v7={corr:+.3f}  DSR={dsr['dsr']:.3f}  PBO={pbo['pbo']}")
    print(f"gates: {''.join('1' if v else '0' for v in gates.values())} "
          f"(g1..g8)  per-year: {[round(x,4) for x in yr_net.values]}")
    print("\nmonth_means (最終10営業日・JPYロング, 3月が突出か):")
    print("  " + "  ".join(f"{m}:{100*v:+.2f}%" for m, v in month_means.items()))


if __name__ == "__main__":
    main()
