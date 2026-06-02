"""イベント・スタディ型バックテスタ + プロップ MC 合格率。

R 単位（リスク正規化リターン）で扱う:
  各トレードの損益を「リスク 1 単位（=ストップ幅 or ボラ単位）の何倍か」で表す。
  これにより異なる資産・ボラ局面を横並びにでき、口座%への換算は
  「per_shot_risk%（1ショットの口座リスク%）× ΣR」で一次に行える（v7 と同じ思想）。

  FX H1 :  ストップ幅 = atr_mult × ATR。R = 方向×(exit-entry)/stopDist − コスト。
  日足   :  リスク単位 = 直近ボラ（標準偏差）。R = 方向×(exit/entry−1)/vol − コスト。
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- FX H1 trades
def _pip_size(close: float, digits_hint: int | None = None) -> float:
    # JPY クロスは 0.01、その他主要は 0.0001 を pip とみなす素朴判定。
    return 0.01 if close >= 20.0 else 0.0001


def event_trades_fx(
    h1: pd.DataFrame, entries, direction: int, hold_h: int,
    atr_period: int = 24, atr_mult: float = 2.5,
    spread_pips: float = 1.0, swap_pips_per_night: float = 0.0,
):
    """FX H1 上で entries（UTC datetime のリスト）に建て、hold_h 時間後に時間決済。
    返り値: DataFrame[time, ret_R]（コスト控除後の R 単位リターン）。
    """
    px = h1["close"].astype(float)
    high = h1["high"].astype(float)
    low = h1["low"].astype(float)
    tr = pd.concat([high - low, (high - px.shift()).abs(), (low - px.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    rows = []
    arr_idx = h1.index
    for t in pd.DatetimeIndex(entries):
        if t not in px.index:
            pos = arr_idx.searchsorted(t)
            if pos >= len(arr_idx):
                continue
            t = arr_idx[pos]
        entry = float(px.loc[t])
        a = float(atr.loc[t]) if not np.isnan(atr.loc[t]) else np.nan
        if not (a > 0):
            continue
        stop_dist = atr_mult * a
        exit_t = t + pd.Timedelta(hours=hold_h)
        epos = arr_idx.searchsorted(exit_t)
        if epos >= len(arr_idx):
            continue
        exit_px = float(px.iloc[epos])
        pip = _pip_size(entry)
        cost_price = spread_pips * pip + swap_pips_per_night * pip * max(1, hold_h // 24)
        raw = direction * (exit_px - entry) - cost_price
        rows.append((t, raw / stop_dist))
    return pd.DataFrame(rows, columns=["time", "ret_R"])


# ------------------------------------------------------------- daily trades
def event_trades_daily(
    d: pd.DataFrame, entries, direction_map, hold_d: int = 1,
    vol_window: int = 20, cost_frac: float = 0.0005,
):
    """日足上で entries（日付）に建て hold_d 日後に決済。
    direction_map: {日付: +1/-1} または一定 int。リスク単位 = 直近 vol_window 日の対数リターン標準偏差。
    cost_frac: 片道コスト（価格比、往復は ×2 相当を内部加算）。
    返り値: DataFrame[time, ret_R]。
    """
    px = d["close"].astype(float)
    ret = np.log(px / px.shift())
    vol = ret.rolling(vol_window).std()
    idx = px.index
    rows = []
    for t in pd.DatetimeIndex(entries):
        if t not in px.index:
            pos = idx.searchsorted(t)
            if pos >= len(idx):
                continue
            t = idx[pos]
        v = float(vol.loc[t]) if not np.isnan(vol.loc[t]) else np.nan
        if not (v > 0):
            continue
        epos = idx.searchsorted(t) + hold_d
        if epos >= len(idx):
            continue
        entry, exit_px = float(px.loc[t]), float(px.iloc[epos])
        d_ = direction_map[t] if hasattr(direction_map, "__getitem__") and not isinstance(direction_map, int) else direction_map
        r = d_ * (exit_px / entry - 1.0) - 2.0 * cost_frac
        rows.append((t, r / v))
    return pd.DataFrame(rows, columns=["time", "ret_R"])


# ------------------------------------------------------------- aggregation
def daily_R(trades: pd.DataFrame) -> pd.Series:
    """トレード R を暦日に集約（同日複数ショットは合算）。index=日, value=ΣR。"""
    if trades.empty:
        return pd.Series(dtype=float)
    s = trades.copy()
    s["day"] = pd.DatetimeIndex(s["time"]).tz_convert("UTC").normalize()
    return s.groupby("day")["ret_R"].sum().sort_index()


# ------------------------------------------------------------- prop MC
def mc_pass_rate(
    daily_R_series: pd.Series, per_shot_risk_pct: float,
    init: float = 100000.0, target_pct: float = 8.0,
    dd_pct: float = 10.0, daily_dd_pct: float | None = 5.0,
    horizon_days: int = 63, n_sims: int = 5000,
    trailing: bool = False, block: int = 5, seed: int = 0,
):
    """ブロック・ブートストラップで口座パスを生成し、目標到達 vs 失格を判定。
    daily_R_series を口座%日次に換算: pct = ΣR × per_shot_risk_pct/100。
    返り値: 合格率（0..1）と中央値到達日数。
    """
    R = np.asarray(daily_R_series.values, dtype=float)
    if len(R) < block + 1:
        return {"pass_rate": float("nan"), "median_days": None}
    rng = np.random.default_rng(seed)
    scale = per_shot_risk_pct / 100.0
    n_blocks = int(np.ceil(horizon_days / block))
    target_eq = init * (1 + target_pct / 100.0)
    passes, days_to_target = 0, []
    starts_pool = len(R) - block
    for _ in range(n_sims):
        starts = rng.integers(0, starts_pool, size=n_blocks)
        path_R = np.concatenate([R[s:s + block] for s in starts])[:horizon_days]
        eq = init
        peak = init
        floor = init * (1 - dd_pct / 100.0)
        breached = reached = False
        for i, r in enumerate(path_R):
            day_pnl = init * r * scale       # 日次集約済み → 1ステップ=1営業日の損益
            if daily_dd_pct is not None and day_pnl <= -init * daily_dd_pct / 100.0:
                breached = True              # 日次ストップ抵触
                break
            eq += day_pnl
            if trailing:
                peak = max(peak, eq)
                floor = max(floor, min(peak - init * dd_pct / 100.0, init))
            if eq <= floor:
                breached = True
                break
            if eq >= target_eq:
                reached = True
                days_to_target.append(i + 1)
                break
        if reached and not breached:
            passes += 1
    return {
        "pass_rate": passes / n_sims,
        "median_days": float(np.median(days_to_target)) if days_to_target else None,
    }
