"""
edge3a_eqmr_10y.py — E3A: 株価指数 短期平均回帰（事前登録 docs/26 §3 E3A）

固定ルール（LOCK 済・変更不可）:
  対象: US500, NAS100, JP225
  シグナルA (gap fade): 前日終値→当日寄りの下方ギャップ < -1.0σ(60日) で寄り LONG・当日引け決済。
  シグナルB (RSI2)    : 2日RSI(終値) < 10 で翌日 LONG・RSI>50 or 2日経過で決済。
  SHORT 対称 (gap>+1σ / RSI>90) は **プラセボ**（弱くてよい）。
  災害ストップ 2.5×日次ATR（左テール対策）。
想定 v7 相関 ≈ 0（別資産・逆張り）。
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data_io import load_h1, to_daily, load_v7_weekly, load_costs, cost_for, DATA_DIR, report_path
from edge_harness import Trades, evaluate_edge, write_result_json

INDICES = ["US500", "NAS100", "JP225"]
GAP_SIGMA = 1.0
RSI_LEN = 2
ATR_LEN = 14
CAT_ATR = 2.5
RISK_BUDGET_PCT = 0.6


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(daily: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = daily["high"], daily["low"], daily["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _capped_ret(direction: int, entry: float, exit_px: float, atr_px: float) -> float:
    """災害ストップでクリップした名目リターン（小数）。"""
    raw = direction * (exit_px - entry) / entry
    stop_frac = CAT_ATR * atr_px / entry
    return max(raw, -stop_frac)


def generate_trades(side: str = "long") -> pd.DataFrame:
    """side='long' が本登録シグナル、'short' はプラセボ（対称）。"""
    sgn = 1 if side == "long" else -1
    rows = []
    costs = load_costs()
    for sym in INDICES:
        d = to_daily(load_h1(sym))
        gap = d["open"] / d["close"].shift(1) - 1.0
        gsig = gap.rolling(60).std()
        a = atr(d, ATR_LEN)
        r = rsi(d["close"], RSI_LEN)

        # --- シグナルA: gap fade ---
        for t in d.index:
            g, gs = gap.get(t, np.nan), gsig.get(t, np.nan)
            if np.isnan(g) or np.isnan(gs) or gs == 0:
                continue
            trig = (g < -GAP_SIGMA * gs) if side == "long" else (g > GAP_SIGMA * gs)
            if not trig:
                continue
            entry, exit_px, av = d["open"][t], d["close"][t], a.get(t, np.nan)
            if np.isnan(av):
                continue
            ret = _capped_ret(sgn, entry, exit_px, av)
            rows.append((t, t, f"{sym}", sgn, ret,
                         cost_for(sym, nights=0, costs=costs)))

        # --- シグナルB: RSI2 逆張り（翌日エントリ・RSI>50 or 2日で決済）---
        idx = list(d.index)
        for i in range(len(idx) - 3):
            t = idx[i]
            rv = r.get(t, np.nan)
            if np.isnan(rv):
                continue
            trig = (rv < 10) if side == "long" else (rv > 90)
            if not trig:
                continue
            entry = d["open"][idx[i + 1]]
            exit_i = i + 3  # 既定: 2日後の引け
            for j in range(i + 1, min(i + 3, len(idx))):
                rj = r.get(idx[j], np.nan)
                if not np.isnan(rj) and ((side == "long" and rj > 50) or (side == "short" and rj < 50)):
                    exit_i = j
                    break
            exit_i = min(exit_i, len(idx) - 1)
            exit_px, av = d["close"][idx[exit_i]], a.get(t, np.nan)
            if np.isnan(av):
                continue
            ret = _capped_ret(sgn, entry, exit_px, av)
            nights = max((idx[exit_i] - idx[i + 1]).days, 0)
            rows.append((idx[i + 1], idx[exit_i], f"{sym}", sgn, ret,
                         cost_for(sym, nights=nights, costs=costs)))

    df = pd.DataFrame(rows, columns=["entry_time", "exit_time", "symbol",
                                     "direction", "ret_gross", "cost"])
    return df


def main():
    long_df = generate_trades("long")
    short_df = generate_trades("short")
    trades = Trades(long_df)
    v7 = load_v7_weekly()

    # ④ プラセボ特異性: 本登録(long 逆張り)のネット平均が SHORT 対称より明確に大きい
    def placebo():
        long_mean = (long_df["ret_gross"] - long_df["cost"]).mean()
        short_mean = (short_df["ret_gross"] - short_df["cost"]).mean()
        return bool(long_mean > 0 and long_mean > short_mean)

    res = evaluate_edge("E3A_eqmr", trades, v7, risk_budget_pct=RISK_BUDGET_PCT,
                        placebo_fn=placebo, alpha=0.0125)
    write_result_json(res, report_path("edge3a_result.json"))


if __name__ == "__main__":
    main()
