"""断面（cross-sectional）ロング・ショート・バックテスタ。

複数資産の中で相対的に強い/弱いものをランクし、上位 LONG・下位 SHORT する
古典的ファクター（断面モメンタム等）を R 単位日次系列で評価する。
docs23 の多資産トレンド・edge2 の XSMOM(MA4=REJECT) を、専用 universe で再検する用途。
"""
import numpy as np
import pandas as pd

from . import data as _data


def load_universe(names, invert=()):
    """{name: close系列} を共通日付で返す。invert に入れた名前は符号反転
    （USDXXX を「XXX 通貨の対USDリターン」に直す等）。日足前提。
    """
    cols = {}
    for n in names:
        if not _data.available(n, "d"):
            continue
        s = _data.load_daily(n)["close"].astype(float)
        cols[n] = s
    px = pd.DataFrame(cols).sort_index().dropna(how="all").ffill()
    rets = np.log(px / px.shift())
    for n in invert:
        if n in rets:
            rets[n] = -rets[n]            # 対USDの符号をそろえる
    return px, rets


def cross_sectional_momentum(
    rets: pd.DataFrame, lookback: int = 63, frac: float = 0.34,
    rebalance: int = 21, cost_frac: float = 0.0005,
):
    """断面モメンタム L/S の日次 R。
    rets: 各資産の日次対数リターン（符号は「ロングしたい方向」に揃え済み）。
    lookback 日の累積リターンでランク → 上位 frac を LONG / 下位 frac を SHORT。
    rebalance 日ごとにウェイト更新、その間は保持。ターンオーバーに cost_frac を課す。
    返り値: 日次 R 系列（ポートフォリオ日次PnLを直近ボラで正規化）。
    """
    r = rets.dropna(how="all")
    mom = r.rolling(lookback).sum()
    idx = r.index
    n_assets = r.shape[1]
    k = max(1, int(round(frac * n_assets)))
    weights = pd.DataFrame(0.0, index=idx, columns=r.columns)
    cur = pd.Series(0.0, index=r.columns)
    for i in range(lookback, len(idx)):
        if (i - lookback) % rebalance == 0:
            m = mom.iloc[i - 1].dropna()
            if len(m) >= 2 * k:
                order = m.sort_values()
                longs = order.index[-k:]
                shorts = order.index[:k]
                cur = pd.Series(0.0, index=r.columns)
                cur[longs] = 1.0 / k
                cur[shorts] = -1.0 / k
        weights.iloc[i] = cur.values
    # 日次 PnL = 前日ウェイト × 当日リターン
    pnl = (weights.shift(1) * r).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    pnl = pnl - cost_frac * turnover
    pnl = pnl.iloc[lookback:]
    vol = pnl.rolling(20).std()
    daily_R = (pnl / vol).replace([np.inf, -np.inf], np.nan).dropna()
    return daily_R
