"""v7（月曜JPYクロス多ショット）の週次 R 系列を再現する。
3本目・4本目候補の「v7 との相関」ゲート用の基準系列を作るのが目的。

ルール（docs/26 / EA v7）:
  EURJPY/GBPJPY/USDJPY を月曜 04/06/08/10 UTC に LONG、各 24h 時間決済。
  リスク単位 = atr_mult×ATR(H1,24)。週次 R = その週の全ショット R の合計。
"""
import numpy as np
import pandas as pd

from . import data as _data
from . import engine as _engine

V7_PAIRS = ("EURJPY", "GBPJPY", "USDJPY")
V7_HOURS = (4, 6, 8, 10)


def monday_entries(index: pd.DatetimeIndex):
    idx = pd.DatetimeIndex(index)
    mon = idx[(idx.dayofweek == 0) & (idx.hour.isin(V7_HOURS))]
    return mon


def v7_weekly_R(pairs=V7_PAIRS, atr_mult: float = 2.5, spread_pips: float = 1.0):
    """v7 の週次 R 系列（index=ISO 週の月曜, value=ΣR）を返す。
    データが無いペアはスキップ。1ペアも無ければ空 Series。
    """
    all_trades = []
    for p in pairs:
        if not _data.available(p, "h1"):
            continue
        h1 = _data.load_h1(p)
        entries = monday_entries(h1.index)
        tr = _engine.event_trades_fx(
            h1, entries, direction=+1, hold_h=24,
            atr_mult=atr_mult, spread_pips=spread_pips,
        )
        all_trades.append(tr)
    if not all_trades:
        return pd.Series(dtype=float)
    trades = pd.concat(all_trades, ignore_index=True)
    d = _engine.daily_R(trades)
    # 週次（月曜起点）に集約
    weekly = d.groupby(pd.Grouper(freq="W-MON", label="left")).sum()
    return weekly


def v7_weekly_R_daily_proxy(pairs=V7_PAIRS, vol_window: int = 20):
    """円クロス H1 が無い場合の v7 相関用プロキシ。
    日足の月曜終値→翌営業日終値を LONG 保有し、直近ボラで正規化した R を週次集約。
    ※あくまで【相関ゲート(G6)用の近似】。v7 自体の検証は H1 が前提（docs/18）。
    """
    parts = []
    for p in pairs:
        if not _data.available(p, "d"):
            continue
        c = _data.load_daily(p)["close"].astype(float)
        ret = np.log(c / c.shift())
        vol = ret.rolling(vol_window).std()
        idx = c.index
        mondays = idx[pd.DatetimeIndex(idx).dayofweek == 0]
        rows = []
        for t in mondays:
            pos = idx.searchsorted(t)
            if pos + 1 >= len(idx):
                continue
            v = float(vol.iloc[pos]) if not np.isnan(vol.iloc[pos]) else np.nan
            if not (v > 0):
                continue
            rows.append((idx[pos], (float(c.iloc[pos + 1] / c.iloc[pos]) - 1.0) / v))
        if rows:
            parts.append(pd.Series([r for _, r in rows],
                                   index=pd.DatetimeIndex([t for t, _ in rows])))
    if not parts:
        return pd.Series(dtype=float)
    allp = pd.concat(parts).groupby(level=0).sum()
    return allp.groupby(pd.Grouper(freq="W-MON", label="left")).sum()


def v7_weekly_R_auto():
    """H1 があれば精密版、無ければ日足プロキシ。返り値: (weekly, source)。"""
    w = v7_weekly_R()
    if not w.empty:
        return w, "H1"
    return v7_weekly_R_daily_proxy(), "daily_proxy"


def corr_with_v7(strategy_daily_R: pd.Series) -> float:
    """戦略の日次 R を週次に集約し v7 週次 R と相関を取る。
    H1 が無ければ日足プロキシで代替。どちらも無ければ NaN（G6 は保守側に倒れる）。
    """
    from . import stats as _stats
    v7w, _src = v7_weekly_R_auto()
    if v7w.empty or strategy_daily_R is None or len(strategy_daily_R) == 0:
        return float("nan")
    sw = strategy_daily_R.groupby(pd.Grouper(freq="W-MON", label="left")).sum()
    j = pd.concat([sw, v7w], axis=1, join="inner").dropna()
    if len(j) < 8:
        return float("nan")
    return _stats.correlation(j.iloc[:, 0].values, j.iloc[:, 1].values)
