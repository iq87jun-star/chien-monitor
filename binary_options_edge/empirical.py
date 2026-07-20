"""原資産の公開データのみで完結する実証検証（IG気配不要）。

検証A: 日内ボラ季節性の実測(H2前提の係数を仮定値→実測値へ)
検証B: ボラ予測可能性の上限測定(H1の必要条件テスト)
検証C: 指標イベントのジャンプσ_J実測(H3の較正)

データ源: Yahoo Finance chart API(認証不要)。60分足×約730日、5分足×約60日。
ネットワーク結果は scratchpad にキャッシュし再実行を高速化する。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

_UA = {"User-Agent": "Mozilla/5.0"}
CACHE_DIR = os.environ.get("BOE_CACHE_DIR", "/tmp/boe_cache")


# --------------------------------------------------------------------------- #
# データ取得
# --------------------------------------------------------------------------- #
def fetch_yahoo(symbol: str, range_: str, interval: str) -> pd.DataFrame:
    """Yahoo chart APIからOHLCを取得(UTC index)。scratchpadにキャッシュ。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{symbol.replace('=','_')}_{range_}_{interval}.json")
    if os.path.exists(cache):
        with open(cache) as f:
            raw = json.load(f)
    else:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                         params={"range": range_, "interval": interval},
                         headers=_UA, timeout=60)
        r.raise_for_status()
        raw = r.json()
        with open(cache, "w") as f:
            json.dump(raw, f)
    res = raw["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "ts": pd.to_datetime(res["timestamp"], unit="s", utc=True),
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
    }).dropna().set_index("ts")
    return df


def log_returns(df: pd.DataFrame, max_gap_factor: float = 1.5,
                interval_seconds: float = 3600.0) -> pd.Series:
    """連続バー間のみの対数リターン(週末・欠測ギャップを除外)。"""
    lr = np.log(df["close"]).diff()
    gaps = df.index.to_series().diff().dt.total_seconds()
    return lr[(gaps <= interval_seconds * max_gap_factor)].dropna()


# --------------------------------------------------------------------------- #
# 検証A: 日内季節性
# --------------------------------------------------------------------------- #
def seasonality_profile(returns_60m: pd.Series) -> pd.DataFrame:
    """UTC時間帯別の実現ボラ係数(全体平均比)。"""
    df = pd.DataFrame({"lr": returns_60m})
    df["hour"] = df.index.hour
    overall = float(np.sqrt(np.mean(df["lr"] ** 2)))
    rows = []
    for h, sub in df.groupby("hour"):
        vol = float(np.sqrt(np.mean(sub["lr"] ** 2)))
        rows.append({"utc_hour": h, "jst_hour": (h + 9) % 24, "n": len(sub),
                     "vol_factor": vol / overall})
    return pd.DataFrame(rows).sort_values("utc_hour").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 検証B: ボラ予測可能性(H1必要条件)
# --------------------------------------------------------------------------- #
def build_vol_dataset(returns_5m: pd.Series, seasonal: pd.DataFrame) -> pd.DataFrame:
    """毎正時を意思決定時点とし、トレーリング(1h/6h/24h)と将来2h実現ボラを対にする。"""
    r2 = returns_5m ** 2
    idx = returns_5m.index
    hours = pd.date_range(idx.min().ceil("h"), idx.max().floor("h"), freq="1h")
    sf = dict(zip(seasonal["utc_hour"], seasonal["vol_factor"]))
    rows = []
    for t in hours:
        def rv(start, end, min_bars):
            w = r2[(idx > start) & (idx <= end)]
            return float(np.sqrt(w.mean())) if len(w) >= min_bars else np.nan
        trail1 = rv(t - timedelta(hours=1), t, 10)
        trail6 = rv(t - timedelta(hours=6), t, 50)
        trail24 = rv(t - timedelta(hours=24), t, 200)
        fut2 = rv(t, t + timedelta(hours=2), 20)
        # 将来2h窓の季節係数(2時間の平均)
        s_fut = np.mean([sf.get(int((t + timedelta(hours=k)).hour), 1.0) for k in (0, 1)])
        s_now = sf.get(int(t.hour), 1.0)
        if all(np.isfinite(v) and v > 0 for v in (trail1, trail6, trail24, fut2)):
            rows.append({"t": t, "trail1": trail1, "trail6": trail6,
                         "trail24": trail24, "fut2": fut2,
                         "seas_now": s_now, "seas_fut": s_fut})
    return pd.DataFrame(rows)


def forecastability(ds: pd.DataFrame, train_frac: float = 0.7) -> dict:
    """ナイーブ(トレーリング1h) vs 季節調整 vs HAR+季節 のOOS予測力と、
    「ナイーブMMとの予測乖離」がε*閾値を超える頻度を測る。"""
    n_train = int(len(ds) * train_frac)
    tr, te = ds.iloc[:n_train], ds.iloc[n_train:]

    y_tr = np.log(tr["fut2"].to_numpy())
    y_te = np.log(te["fut2"].to_numpy())

    def rmse(pred_log, actual_log):
        return float(np.sqrt(np.mean((pred_log - actual_log) ** 2)))

    # 1) ナイーブ: σ_pred = trail1
    naive_te = np.log(te["trail1"].to_numpy())
    # 2) 季節調整: trail1 × (季節係数_将来窓/係数_現在)
    seas_te = np.log(te["trail1"].to_numpy() * te["seas_fut"].to_numpy()
                     / te["seas_now"].to_numpy())
    # 3) HAR+季節: log σ_fut ~ log trail1 + log trail6 + log trail24 + log(seas_fut)
    def design(d):
        return np.column_stack([np.ones(len(d)), np.log(d["trail1"]),
                                np.log(d["trail6"]), np.log(d["trail24"]),
                                np.log(d["seas_fut"] / d["seas_now"])])
    beta, *_ = np.linalg.lstsq(design(tr), y_tr, rcond=None)
    har_te = design(te) @ beta

    # ナイーブMM(トレーリング価格付け)に対する、モデル側の予測乖離の頻度
    dis = np.abs(np.exp(har_te) / te["trail1"].to_numpy() - 1.0)
    # モデル自身の残り誤差(=これ以上は誰にも予測できない部分の推定)
    resid = np.abs(np.exp(har_te) / te["fut2"].to_numpy() - 1.0)
    return {
        "n_train": n_train, "n_test": len(te),
        "rmse_log_naive": rmse(naive_te, y_te),
        "rmse_log_seasonal": rmse(seas_te, y_te),
        "rmse_log_har": rmse(har_te, y_te),
        "median_abs_mismatch_naive": float(np.median(np.abs(te["fut2"] / te["trail1"] - 1))),
        "disagree_vs_naive_median": float(np.median(dis)),
        "disagree_gt_6.2%": float(np.mean(dis > 0.062)),
        "disagree_gt_12.4%": float(np.mean(dis > 0.124)),
        "model_residual_median": float(np.median(resid)),
        "beta": beta.tolist(),
    }


# --------------------------------------------------------------------------- #
# 検証C: イベントジャンプ較正
# --------------------------------------------------------------------------- #
def _us_dst(d: date) -> bool:
    """米夏時間(3月第2日曜〜11月第1日曜)の近似判定。"""
    def nth_sunday(year, month, n):
        d0 = date(year, month, 1)
        off = (6 - d0.weekday()) % 7
        return d0 + timedelta(days=off + 7 * (n - 1))
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def _first_friday(year: int, month: int) -> date:
    d0 = date(year, month, 1)
    return d0 + timedelta(days=(4 - d0.weekday()) % 7)


def build_event_calendar(start: date, end: date) -> pd.DataFrame:
    """NFP/CPI/FOMCのUTC発表時刻(確度の高いもののみ。2025年10-12月は閉鎖の影響で除外)。"""
    events = []
    # NFP: 第1金曜 8:30 ET(1月と祝日例外は既知分のみ補正)
    overrides = {(2025, 1): date(2025, 1, 10), (2026, 1): date(2026, 1, 9),
                 (2026, 7): date(2026, 7, 2)}
    m = date(start.year, start.month, 1)
    while m <= end:
        if not (m.year == 2025 and m.month >= 10):   # 閉鎖期は日付不確実→除外
            d = overrides.get((m.year, m.month), _first_friday(m.year, m.month))
            if start <= d <= end:
                events.append(("NFP", d, 8.5))
        m = (m.replace(day=28) + timedelta(days=5)).replace(day=1)
    # CPI: 8:30 ET(確認済み日付のみ)
    cpi = [date(2024, 8, 14), date(2024, 9, 11), date(2024, 10, 10),
           date(2024, 11, 13), date(2024, 12, 11),
           date(2025, 1, 15), date(2025, 2, 12), date(2025, 3, 12),
           date(2025, 4, 10), date(2025, 5, 13), date(2025, 6, 11),
           date(2025, 7, 15), date(2025, 8, 12), date(2025, 9, 11),
           date(2026, 1, 13), date(2026, 2, 13), date(2026, 3, 11),
           date(2026, 4, 10), date(2026, 5, 12), date(2026, 6, 10),
           date(2026, 7, 14)]
    events += [("CPI", d, 8.5) for d in cpi if start <= d <= end]
    # FOMC: 声明 14:00 ET
    fomc = [date(2024, 7, 31), date(2024, 9, 18), date(2024, 11, 7), date(2024, 12, 18),
            date(2025, 1, 29), date(2025, 3, 19), date(2025, 5, 7), date(2025, 6, 18),
            date(2025, 7, 30), date(2025, 9, 17), date(2025, 10, 29), date(2025, 12, 10),
            date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17)]
    events += [("FOMC", d, 14.0) for d in fomc if start <= d <= end]
    rows = []
    for name, d, et_hour in events:
        utc_hour = et_hour + (4 if _us_dst(d) else 5)
        rows.append({"event": name, "date": d,
                     "utc": datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                     + timedelta(hours=utc_hour)})
    return pd.DataFrame(rows).sort_values("utc").reset_index(drop=True)


def event_jump_hourly(returns_60m: pd.Series, calendar: pd.DataFrame) -> pd.DataFrame:
    """発表を含む1時間バーのリターンと、同一UTC時刻の非イベント日ベースラインから
    σ_J = √max(σ_event² − σ_base², 0) を推定。"""
    lr = returns_60m
    bar_of = {}   # イベント→そのイベントを含むバーのリターン
    for _, ev in calendar.iterrows():
        # 発表時刻を(開始, 終了]に含むバー: index はバー終了時刻ではなく開始時刻の場合が
        # あるため両解釈で最近傍を取る。Yahooの60分足はバー開始時刻ラベル。
        bar_start = ev["utc"].replace(minute=0, second=0)
        if bar_start in lr.index:
            bar_of[(ev["event"], ev["date"])] = float(lr.loc[bar_start])
    df = pd.DataFrame({"lr": lr})
    df["hour"] = df.index.hour
    df["d"] = df.index.date
    event_days = set(calendar["date"])
    rows = []
    for name in calendar["event"].unique():
        evs = [(k, v) for k, v in bar_of.items() if k[0] == name]
        if not evs:
            continue
        ev_r = np.array([v for _, v in evs])
        hours = {calendar[(calendar["event"] == name)].iloc[0]["utc"].hour}
        hours = set(calendar[calendar["event"] == name]["utc"].dt.hour)
        base = df[(df["hour"].isin(hours)) & (~df["d"].isin(event_days))]["lr"]
        s_ev = float(np.sqrt(np.mean(ev_r ** 2)))
        s_base = float(np.sqrt(np.mean(base ** 2)))
        sigma_j = float(np.sqrt(max(s_ev ** 2 - s_base ** 2, 0.0)))
        rows.append({"event": name, "n_events": len(ev_r), "n_base": len(base),
                     "vol_event_hour": s_ev, "vol_base_hour": s_base,
                     "sigma_j_log": sigma_j,
                     "max_abs_move": float(np.max(np.abs(ev_r)))})
    return pd.DataFrame(rows)


def event_jump_5m(returns_5m: pd.Series, calendar: pd.DataFrame) -> pd.DataFrame:
    """直近60日のイベントについて発表直後10分(5分足2本)の変化を個別に実測。"""
    rows = []
    for _, ev in calendar.iterrows():
        t0 = ev["utc"]
        w = returns_5m[(returns_5m.index > t0 - timedelta(minutes=5))
                       & (returns_5m.index <= t0 + timedelta(minutes=10))]
        if len(w) >= 2:
            move = float(np.sqrt(np.sum(w ** 2)))
            rows.append({"event": ev["event"], "date": ev["date"],
                         "move_10min_log": move})
    return pd.DataFrame(rows)
