"""v7 強化（コア強化）の分析基盤。新エッジ探索ではない。

v7（月曜JPYクロス多ショット）の【日次 R 系列・口座エクイティ・maxDD・合格率】を、
任意の「エントリー・フィルタ」つきで計算し、ベースライン vs フィルタを比較する。

R 単位: 1トレード = リスク atr_mult×ATR の何倍か（v7 EA と同思想）。
口座日次% = Σ(その日のトレード R) × per_shot_risk%。per_shot = weekly_risk / 12。
"""
import numpy as np
import pandas as pd

from . import data as _data
from . import engine as _engine
from . import stats as _stats

PAIRS = ("EURJPY", "GBPJPY", "USDJPY")
HOURS = (4, 6, 8, 10)
SHOTS = 12                       # 3ペア×4時刻


def _pair_trades(pair, atr_mult=2.5, spread_pips=1.0, filt=None):
    """1ペアの月曜ショットを R 付きで返す。filt(entry_time, h1_df)->bool で採否。"""
    h1 = _data.load_h1(pair)
    idx = pd.DatetimeIndex(h1.index)
    entries = idx[(idx.dayofweek == 0) & (idx.hour.isin(HOURS))]
    if filt is not None:
        entries = pd.DatetimeIndex([t for t in entries if filt(t, h1)])
    tr = _engine.event_trades_fx(h1, entries, direction=+1, hold_h=24,
                                 atr_mult=atr_mult, spread_pips=spread_pips)
    return tr


def v7_daily_R(filt=None, pairs=PAIRS, atr_mult=2.5, spread_pips=1.0):
    """全ペア合算の日次 R 系列（filt 適用可）。"""
    frames = [_pair_trades(p, atr_mult, spread_pips, filt) for p in pairs if _data.available(p, "h1")]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.Series(dtype=float)
    trades = pd.concat(frames, ignore_index=True)
    return _engine.daily_R(trades)


def equity_stats(daily_R, weekly_risk_pct, init=100000.0):
    """日次 R を口座%に換算し、累積エクイティ・maxDD・年率・Calmar を返す。"""
    per_shot = weekly_risk_pct / SHOTS
    daily_pct = daily_R * (per_shot / 100.0)
    eq = init * (1.0 + daily_pct).cumprod()
    peak = eq.cummax()
    maxdd = float(((eq - peak) / peak).min())
    years = max(1e-9, (daily_R.index[-1] - daily_R.index[0]).days / 365.25)
    total = float(eq.iloc[-1] / init - 1.0)
    cagr = float((eq.iloc[-1] / init) ** (1 / years) - 1.0)
    calmar = float(cagr / abs(maxdd)) if maxdd < 0 else float("inf")
    return {
        "weekly_risk_pct": weekly_risk_pct,
        "net_total_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "maxDD_pct": round(maxdd * 100, 2),
        "calmar": round(calmar, 2),
        "sharpe": round(_stats.sharpe(daily_R.values), 3),
        "n_days": int(len(daily_R)),
    }


# ----------------------------------------------------------------- フィルタ
def _daily_close(h1):
    return h1["close"].astype(float).resample("1D").last().dropna()


def filter_vix(quantile=0.80, roll=252):
    """VF1: VIX が高分位(リスクオフ)の週はショットを見送る。前営業日の VIX で判定。"""
    vix = _data.load_daily("VIX")["close"].astype(float)
    thr = vix.rolling(roll).quantile(quantile)
    vix_asof = vix.copy()

    def filt(t, h1):
        day = pd.Timestamp(t).normalize()
        prev = vix_asof.index[vix_asof.index < day]
        if len(prev) == 0:
            return True
        last = prev[-1]
        th = thr.get(last, np.nan)
        if np.isnan(th):
            return True
        return bool(vix_asof.get(last, np.nan) <= th)
    return filt


def filter_trend(ma=50):
    """VF2: そのペアの日足終値が MA 超(上昇局面)のときだけ LONG を取る。"""
    cache = {}

    def filt(t, h1):
        key = id(h1)
        if key not in cache:
            dc = _daily_close(h1)
            cache[key] = (dc, dc.rolling(ma).mean())
        dc, mav = cache[key]
        day = pd.Timestamp(t).normalize()
        prev = dc.index[dc.index < day]
        if len(prev) == 0:
            return True
        last = prev[-1]
        m = mav.get(last, np.nan)
        if np.isnan(m):
            return True
        return bool(dc.get(last, np.nan) > m)
    return filt


def filter_pair_vol(quantile=0.80, atrw=20, roll=252):
    """VF3: そのペアの日次ATRが高分位の週は見送る（高ボラ週のテール回避）。"""
    cache = {}

    def filt(t, h1):
        key = id(h1)
        if key not in cache:
            dc = _daily_close(h1)
            atr = dc.diff().abs().rolling(atrw).mean()
            cache[key] = (atr, atr.rolling(roll).quantile(quantile))
        atr, thr = cache[key]
        day = pd.Timestamp(t).normalize()
        prev = atr.index[atr.index < day]
        if len(prev) == 0:
            return True
        last = prev[-1]
        th = thr.get(last, np.nan)
        if np.isnan(th):
            return True
        return bool(atr.get(last, np.nan) <= th)
    return filt


def split_half_equity(daily_R, weekly_risk_pct=1.0):
    """前半/後半それぞれの Calmar・maxDD を返す（改善の頑健性確認）。"""
    years = sorted(set(pd.DatetimeIndex(daily_R.index).year))
    mid = years[len(years) // 2 - 1]
    a = daily_R[pd.DatetimeIndex(daily_R.index).year <= mid]
    b = daily_R[pd.DatetimeIndex(daily_R.index).year > mid]
    return {"first": equity_stats(a, weekly_risk_pct) if len(a) else None,
            "second": equity_stats(b, weekly_risk_pct) if len(b) else None}
