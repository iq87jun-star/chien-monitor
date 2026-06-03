"""
v7_sim.py — v7（月曜JPYクロス多ショット）の予算較正シミュレータ（器II の実測 / docs/29）。

build_v7_weekly.py は相関基準用の等加重リターンだったが、本ファイルは EA と同じ
**サイズ較正**（perShot = 週次予算/12、ストップ=2.5×日次ATR）で口座リターンを組み、
FundedNext ガード下の **10年maxDD** と **Phase1合格率（ブロック・ブートストラップ）** を出す。

- 口座寄与/shot = perShotRisk × clamp(ret24 / stopFrac, ≥ −1)   （災害ストップで損失を−perShotで打切）
- 予算スイープ: 0.5 / 0.6 / 0.75 / 1.0 / 1.5 / 2.5 %/週
- レジーム条件付け（walk-forward）: 前半でボラ閾値を決め、後半のみで「低ボラ週のみ稼働」を検証。
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from data_io import load_h1, to_daily, report_path

PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]
HOURS = [4, 6, 8, 10]
SHOTS_PER_WEEK = 12
CAT_ATR = 2.5
HOLD_H = 24


def shot_table() -> pd.DataFrame:
    """各 (月曜・時刻・ペア) ショットの ret24・stopFrac・MAE(保有中最悪フロート) を集計。"""
    rows = []
    for sym in PAIRS:
        h1 = load_h1(sym)
        close = h1["close"]
        d = to_daily(h1)
        # 日次ATR(14) を前日値で参照（先読み回避）
        pc = d["close"].shift(1)
        tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(),
                        (d["low"] - pc).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().shift(1)
        for t, entry in close.items():
            if t.dayofweek != 0 or t.hour not in HOURS:
                continue
            hold = h1[(h1.index >= t) & (h1.index <= t + pd.Timedelta(hours=HOLD_H))]
            fut = close[close.index >= t + pd.Timedelta(hours=HOLD_H)]
            if len(fut) == 0 or len(hold) < 2:
                continue
            a = atr.get(t.normalize(), np.nan)
            if not np.isfinite(a) or a <= 0 or entry <= 0:
                continue
            ret24 = fut.iloc[0] / entry - 1.0
            mae = hold["low"].min() / entry - 1.0       # LONG 保有中の最悪フロート
            stop_frac = CAT_ATR * a / entry
            rows.append((t, sym, ret24, mae, stop_frac))
    df = pd.DataFrame(rows, columns=["t", "sym", "ret24", "mae", "stop_frac"]).sort_values("t")
    return df


def floating_equity_maxdd(shots: pd.DataFrame, weekly_budget_pct: float,
                          pair_close: dict | None = None) -> float:
    """フロート(含み損)込みの正しい equity 時系列で 10年 maxDD（FundedNext は equity 基準）。

    equity(τ) = Σ_i [ realized_i·1(τ≥exit_i) + floating_i(τ)·1(entry_i≤τ<exit_i) ]。
    重なり(月曜は最大12玉同時保有)を時間グリッド上で正しく合算。災害ストップで -perShot 打切。
    加算法はリターン加算（口座は概ね一定サイズ運用＝v7思想）で近似。
    """
    per = (weekly_budget_pct / 100.0) / SHOTS_PER_WEEK
    if pair_close is None:
        pair_close = {s: load_h1(s)["close"] for s in PAIRS}
    # 時間グリッド = 全ペアのH1タイムスタンプ和集合
    grid = pd.DatetimeIndex(sorted(set().union(*[c.index for c in pair_close.values()])))
    pos = {ts: i for i, ts in enumerate(grid)}
    closes = {s: pair_close[s].reindex(grid).ffill() for s in PAIRS}

    realized_delta = np.zeros(len(grid))
    floating = np.zeros(len(grid))
    for t, sym, ret24, mae, sf in shots[["t", "sym", "ret24", "mae", "stop_frac"]].itertuples(index=False, name=None):
        size = per / sf
        entry_i = pos.get(pd.Timestamp(t))
        if entry_i is None:
            continue
        entry_px = closes[sym].iloc[entry_i]
        exit_ts = pd.Timestamp(t) + pd.Timedelta(hours=HOLD_H)
        # 保有中の各時間の含み損益（-perで打切＝ストップ）
        stopped = False
        realized_val = None
        j = entry_i + 1
        cj = closes[sym]
        while j < len(grid) and grid[j] <= exit_ts:
            fl = size * (cj.iloc[j] / entry_px - 1.0)
            if fl <= -per:
                fl = -per; stopped = True
            floating[j] += fl
            if stopped:
                realized_val = -per
                break
            j += 1
        if realized_val is None:
            realized_val = per * max(ret24 / sf, -1.0)
        exit_i = min(j, len(grid) - 1)
        realized_delta[exit_i] += realized_val
        # 決済時点で floating からは外れる（ループ外なので自然に消える）
    equity = 1.0 + np.cumsum(realized_delta) + floating
    peak = np.maximum.accumulate(equity)
    return float(-np.min((equity - peak) / peak))


def weekly_account_returns(shots: pd.DataFrame, weekly_budget_pct: float) -> pd.Series:
    """週次の口座リターン（小数）。perShot=budget/12、災害ストップで−perShotに打切。"""
    per = (weekly_budget_pct / 100.0) / SHOTS_PER_WEEK
    contrib = per * np.maximum(shots["ret24"] / shots["stop_frac"], -1.0)
    s = pd.Series(contrib.values, index=pd.to_datetime(shots["t"], utc=True))
    return s.resample("W-MON").sum().fillna(0.0)


def max_drawdown(weekly: pd.Series) -> float:
    eq = (1 + weekly).cumprod()
    return float(-((eq - eq.cummax()) / eq.cummax()).min())


def bootstrap_pass_rate(weekly: np.ndarray, n_paths=2000, block=4,
                        target=0.08, floor=0.08, max_weeks=520, seed=0) -> float:
    """ブロック・ブートストラップで Phase1 合格率。

    equity 0 から、+target 到達=合格、−floor 到達(=ピーク無関係の対初期DD)=失格。時間無制限だが
    max_weeks で打切（未達はそのまま継続不能としてカウントせず=分母から除外しない: 失格扱いにしない）。
    """
    rng = np.random.default_rng(seed)
    w = weekly[np.isfinite(weekly)]
    n = len(w)
    if n < block:
        return float("nan")
    passes = 0
    decided = 0
    for _ in range(n_paths):
        eq = 0.0
        wk = 0
        outcome = None
        while wk < max_weeks:
            start = rng.integers(0, n - block)
            for r in w[start:start + block]:
                eq += r
                wk += 1
                if eq >= target:
                    outcome = "pass"; break
                if eq <= -floor:
                    outcome = "fail"; break
            if outcome:
                break
        if outcome:
            decided += 1
            if outcome == "pass":
                passes += 1
    return passes / decided if decided else float("nan")


def main():
    shots = shot_table()
    pair_close = {s: load_h1(s)["close"] for s in PAIRS}
    budgets = [0.5, 0.6, 0.75, 1.0, 1.5, 2.5]
    out = {"period": "2016-01..2025-12", "n_shots": int(len(shots)), "budgets": {}}
    print(f"v7 shots: {len(shots)}  ({shots['t'].min()}..{shots['t'].max()})")
    print(f"{'budget%':>8} {'DDreal%':>8} {'DDfloat%':>9} {'passRate%':>10} {'ann_ret%':>9}")
    for b in budgets:
        wk = weekly_account_returns(shots, b)
        dd_real = max_drawdown(wk)
        dd_float = floating_equity_maxdd(shots, b, pair_close)
        pr = bootstrap_pass_rate(wk.values)
        ann = wk.mean() * 52
        out["budgets"][str(b)] = {"maxDD_realized": dd_real, "maxDD_floating": dd_float,
                                  "pass_rate": pr, "ann_ret": float(ann), "weeks": int(len(wk))}
        print(f"{b:8.2f} {100*dd_real:8.2f} {100*dd_float:9.2f} {100*pr:10.1f} {100*ann:9.2f}")

    # --- レジーム条件付け（walk-forward, 先読みなし）---
    print("\n=== regime conditioning (walk-forward, budget=0.6) ===")
    wk = weekly_account_returns(shots, 0.6)
    # ボラ代理: JPYバスケット週次リターンの 8週ローリング std（前週まで）
    vol = wk.rolling(8).std().shift(1)
    half = len(wk) // 2
    thr = vol.iloc[:half].median()              # 前半でしきい値決定
    oos = wk.iloc[half:]
    oos_vol = vol.iloc[half:]
    base_oos = oos
    cond_oos = oos.where(oos_vol <= thr, 0.0)    # 後半: 低ボラ週のみ稼働
    def stats(s):
        s = s[np.isfinite(s)]
        sd = s.std()
        return dict(mean=float(s.mean()), maxDD=max_drawdown(s),
                    sharpe=float(s.mean()/sd*np.sqrt(52)) if sd>0 else 0.0,
                    active=int((s!=0).sum()))
    b_s, c_s = stats(base_oos), stats(cond_oos)
    out["regime_walkforward"] = {"vol_threshold": float(thr), "baseline_oos": b_s,
                                 "low_vol_only_oos": c_s}
    print(f"  threshold(vol)={thr:.5f}")
    print(f"  baseline  OOS: mean={b_s['mean']:+.5f} maxDD={100*b_s['maxDD']:.2f}% "
          f"sharpe={b_s['sharpe']:.2f} active={b_s['active']}")
    print(f"  lowvol-on OOS: mean={c_s['mean']:+.5f} maxDD={100*c_s['maxDD']:.2f}% "
          f"sharpe={c_s['sharpe']:.2f} active={c_s['active']}")
    verdict = "改善" if (c_s['sharpe'] > b_s['sharpe'] and c_s['maxDD'] <= b_s['maxDD']) else "改善せず"
    out["regime_walkforward"]["verdict"] = verdict
    print(f"  → レジーム条件付けは OOS で: {verdict}")

    with open(report_path("v7_sim.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n[WROTE]", report_path("v7_sim.json"))


if __name__ == "__main__":
    main()
