"""
edge3b_leadlag_10y.py — E3B: クロスアセット・リードラグ（docs/26 §3 E3B）

固定ルール（LOCK 済）:
  先行変数: US500 の前日 16:00-21:00 UTC リターン r。σ = その窓リターンの60日std。
  r > +0.5σ なら 当日 00:00 UTC に AUDJPY・CADJPY を LONG、08:00 UTC 時間決済。
  r < -0.5σ は見送り（SHORT 対称＝プラセボ）。
  対象 AUDJPY/CADJPY は v7（EUR/GBP/USD-JPY）と非重複。
想定 v7 相関: 低（先行条件付き・別ペア・別時刻）。
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data_io import load_h1, load_v7_weekly, load_costs, cost_for, DATA_DIR, report_path
from edge_harness import Trades, evaluate_edge, write_result_json

TARGETS = ["AUDJPY", "CADJPY"]
LEAD = "US500"
SIGMA_K = 0.5
RISK_BUDGET_PCT = 0.6


def lead_window_returns() -> pd.Series:
    """US500 の各日 16:00-21:00 UTC リターン（日付 index）。"""
    h = load_h1(LEAD)
    out = {}
    for day, g in h.groupby(h.index.normalize()):
        w = g.between_time("16:00", "21:00")
        if len(w) >= 2:
            out[day] = w["close"].iloc[-1] / w["close"].iloc[0] - 1.0
    s = pd.Series(out).sort_index()
    return s


def price_at(h1: pd.DataFrame, day: pd.Timestamp, hhmm: str):
    w = h1[h1.index.normalize() == day].between_time(hhmm, hhmm)
    return w["close"].iloc[0] if len(w) else np.nan


def generate_trades(side: str = "long") -> pd.DataFrame:
    sgn = 1 if side == "long" else -1
    lead = lead_window_returns()
    lead_sig = lead.rolling(60).std()
    costs = load_costs()
    rows = []
    data = {s: load_h1(s) for s in TARGETS}
    days = sorted(lead.index)
    for k, day in enumerate(days[:-1]):
        r, sg = lead.get(day, np.nan), lead_sig.get(day, np.nan)
        if np.isnan(r) or np.isnan(sg) or sg == 0:
            continue
        trig = (r > SIGMA_K * sg) if side == "long" else (r < -SIGMA_K * sg)
        if not trig:
            continue
        nxt = days[k + 1]  # 翌「アジア」営業日
        for sym in TARGETS:
            h1 = data[sym]
            entry = price_at(h1, nxt, "00:00")
            exit_px = price_at(h1, nxt, "08:00")
            if np.isnan(entry) or np.isnan(exit_px):
                continue
            ret = sgn * (exit_px - entry) / entry
            rows.append((nxt, nxt, sym, sgn, ret, cost_for(sym, 0, costs)))
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "symbol",
                                       "direction", "ret_gross", "cost"])


def main():
    long_df = generate_trades("long")
    short_df = generate_trades("short")
    trades = Trades(long_df)
    v7 = load_v7_weekly()

    def placebo():
        lm = (long_df["ret_gross"] - long_df["cost"]).mean()
        sm = (short_df["ret_gross"] - short_df["cost"]).mean()
        return bool(lm > 0 and lm > sm)

    res = evaluate_edge("E3B_leadlag", trades, v7, risk_budget_pct=RISK_BUDGET_PCT,
                        placebo_fn=placebo, alpha=0.0125)
    write_result_json(res, report_path("edge3b_result.json"))


if __name__ == "__main__":
    main()
