"""
edge_cot_10y.py — 第3弾（docs/31, LOCKED）COT ポジショニング・コントラリアン 10年検定。

C1: 横断ポジショニング・コントラリアン（z最低3ロング/最高3ショート・ドル中立・週次）
C2: 時系列ポジショニング極値（z>+2→翌週ショート / z<-2→翌週ロング・等加重）
強化ゲート（④ベータ中立 t>2.5 / ⑦Deflated Sharpe N_trials≥50 / ⑧PBO≤0.20）必須。
公表ラグ: COT(火) z を shift(1) して翌週リターンに当てる（先読み回避）。
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from data_io import DATA_DIR, load_v7_weekly, report_path
from edge_b_10y import weekly_ret_vs_usd, usd_factor_weekly, as_weekly_trades, evaluate_b

COT_CCY = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
ALPHA = 0.025
N_TRIALS = 50


def cot_z(zwin=156) -> pd.DataFrame:
    """spec_net% の週次(W-MON) z スコア（過去窓のみ・shift済）。"""
    df = pd.read_csv(f"{DATA_DIR}/cot_fx.csv", parse_dates=["date"])
    w = df.pivot_table(index="date", columns="ccy", values="spec_net_pct")
    w = w.resample("W-MON").last()
    mu = w.rolling(zwin, min_periods=52).mean()
    sd = w.rolling(zwin, min_periods=52).std()
    z = (w - mu) / sd
    return z.shift(1)                       # 公表+執行ラグ（翌週に建てる）


def c1_weekly(n_leg=3, zwin=156) -> pd.Series:
    z = cot_z(zwin)
    ret = weekly_ret_vs_usd()[COT_CCY]
    z, ret = z.align(ret, join="inner")
    out = {}
    for wk in z.index:
        zz = z.loc[wk].dropna()
        if len(zz) < 2 * n_leg:
            continue
        order = zz.sort_values()
        longs = order.index[:n_leg]          # 売り込み過ぎ→ロング
        shorts = order.index[-n_leg:]        # 買い込み過ぎ→ショート
        r = ret.loc[wk]
        if r[list(longs) + list(shorts)].isna().any():
            continue
        out[wk] = float(r[longs].mean() - r[shorts].mean())
    return (pd.Series(out).sort_index() - 0.0001).rename("C1")


def c2_weekly(z_entry=2.0, z_exit=0.5, max_hold=4, zwin=156) -> pd.Series:
    z = cot_z(zwin)
    ret = weekly_ret_vs_usd()[COT_CCY]
    z, ret = z.align(ret, join="inner")
    idx = list(z.index)
    pnl = pd.Series(0.0, index=z.index)
    cnt = pd.Series(0, index=z.index)
    for c in COT_CCY:
        i = 0
        while i < len(idx):
            zi = z[c].iloc[i]
            if np.isfinite(zi) and abs(zi) >= z_entry:
                direction = -1 if zi > 0 else +1     # コントラリアン
                j = i
                held = 0
                while j < len(idx) and held < max_hold:
                    r = ret[c].iloc[j]
                    if np.isfinite(r):
                        pnl.iloc[j] += direction * r - 0.0001
                        cnt.iloc[j] += 1
                    held += 1
                    j += 1
                    if j < len(idx) and np.isfinite(z[c].iloc[j]) and abs(z[c].iloc[j]) <= z_exit:
                        break
                i = j
            else:
                i += 1
    avg = (pnl / cnt.replace(0, np.nan)).dropna()    # 稼働通貨で等加重
    return avg.rename("C2")


def main():
    market = usd_factor_weekly()
    v7 = load_v7_weekly()
    specs = {
        "C1_cot_xsection": dict(
            main=c1_weekly(), cost=0.0001,
            variants=[c1_weekly(n, zw) for n in (2, 3) for zw in (104, 156, 208)]),
        "C2_cot_extreme": dict(
            main=c2_weekly(), cost=0.0001,
            variants=[c2_weekly(ze, 0.5, mh) for ze in (1.5, 2.0, 2.5) for mh in (3, 4, 6)]),
    }
    rows = []
    for eid, sp in specs.items():
        res = evaluate_b(eid, sp["main"], sp["variants"], market, v7, sp["cost"])
        with open(report_path(f"{eid.lower()}_result.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        rows.append({"edge": eid, "grade": res["grade"], "n": res["n_trades"],
                     "net": round(res["net_profit_10y"], 4), "p": round(res["perm_p_net"], 4),
                     "t_alpha": round(res["t_alpha"], 2), "dsr": round(res["dsr"], 3),
                     "pbo": round(res["pbo"], 3) if np.isfinite(res["pbo"]) else None,
                     "corr_v7": round(res["corr_v7"], 3)})
    print("\n=== COT positioning 10-year verdict | alpha=0.025, N_trials=50 ===")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
