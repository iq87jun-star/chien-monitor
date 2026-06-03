"""
ma2.py — 2本目候補 MA2（金+株指数の月次TSMOM）の再現とサイズ算定（デモ前進検証用）。

仕様（経緯ブランチ docs/23 / edge5_multiasset_10y.py）:
  資産 = XAUUSD(金) / US500 / NAS100 / GER40。暗号除外。
  シグナル = 各月、過去{1,3,6,12}ヶ月リターンの sign の合計 comp → pos=sign(comp)（順方向）。
  保有 = 翌月。等加重。月次リバランス。
出力: 10年の net/maxDD、ボラ正規化の質、v7相関、−10%口座向け縮小サイズ。
"""
from __future__ import annotations

import datetime as dt
import os
import numpy as np
import pandas as pd

from data_io import load_h1, load_v7_weekly, DATA_DIR

LOOKBACKS = [1, 3, 6, 12]
COST_BPS = 3.0  # 月次リバランス1回転の往復コスト概算（金/指数CFD）

DUKA = {"XAUUSD": "XAU/USD", "GER40": "DEU.IDX/EUR"}


def daily_close(asset: str) -> pd.Series:
    """XAU/GER40 は Dukascopy 日足を取得・キャッシュ。US500/NAS100 はローカルH1→日足。"""
    if asset in ("US500", "NAS100"):
        return load_h1(asset)["close"].resample("1D").last().dropna()
    path = os.path.join(DATA_DIR, f"{asset}_d.csv")
    if os.path.exists(path):
        s = pd.read_csv(path, parse_dates=["time"]).set_index("time")["close"]
        return s
    import dukascopy_python as dk
    df = dk.fetch(DUKA[asset], dk.INTERVAL_DAY_1, dk.OFFER_SIDE_BID,
                  dt.datetime(2016, 1, 1), dt.datetime(2025, 12, 31))
    s = df["close"]; s.index.name = "time"
    s.to_frame("close").to_csv(path)
    return s


def ma2_monthly() -> pd.Series:
    assets = ["XAUUSD", "US500", "NAS100", "GER40"]
    legs = {}
    for a in assets:
        m = daily_close(a).resample("ME").last().dropna()
        if len(m) < max(LOOKBACKS) + 3:
            continue
        comp = sum(np.sign(m.pct_change(L)) for L in LOOKBACKS)
        pos = np.sign(comp)
        nxt = m.pct_change().shift(-1)
        turn = pos.diff().abs().fillna(0)            # ポジ転換でコスト
        legs[a] = (pos * nxt - turn * COST_BPS / 1e4).dropna()
    df = pd.DataFrame(legs)
    return df.mean(axis=1).dropna()                  # 等加重


def maxdd(monthly: pd.Series) -> float:
    eq = (1 + monthly).cumprod()
    return float(-((eq - eq.cummax()) / eq.cummax()).min())


def main():
    r = ma2_monthly()
    net = float(((1 + r).prod() - 1) * 100)
    dd = maxdd(r) * 100
    ann_vol = float(r.std() * np.sqrt(12) * 100)
    ann_ret = float(r.mean() * 12 * 100)
    sharpe = ann_ret / ann_vol if ann_vol else 0.0

    # v7 相関（月次）
    v7w = load_v7_weekly()
    v7m = v7w.resample("ME").sum()
    a, b = r.align(v7m, join="inner")
    corr = float(np.corrcoef(a.values, b.values)[0, 1]) if len(a) >= 12 and a.std() > 0 else float("nan")

    print("=== MA2 reproduction (金+US500+NAS100+GER40, 月次TSMOM) ===")
    print(f"months={len(r)}  net_10y={net:+.1f}%  maxDD={dd:.1f}%  "
          f"annRet={ann_ret:+.1f}%  annVol={ann_vol:.1f}%  Sharpe={sharpe:.2f}")
    print(f"corr_v7(monthly)={corr:+.3f}  win_rate={100*(r>0).mean():.0f}%")

    # --- −10%口座向け縮小サイズ（DDは~サイズ線形と仮定） ---
    print("\n=== −10%口座向けサイズ算定（衛星・DD予算を割当） ===")
    for budget in (2.0, 3.0, 4.0):
        scale = budget / dd
        print(f"  MA2のDD予算 {budget:.0f}% → 縮小率 {scale:.2f}x "
              f"（年率{ann_ret*scale:+.1f}% / 年率vol{ann_vol*scale:.1f}% で運用）")

    # --- 現在の建玉シグナル（デモ実行用） ---
    print("\n=== 現在のMA2建玉シグナル（毎月末リバランス） ===")
    for a in ["XAUUSD", "US500", "NAS100", "GER40"]:
        m = daily_close(a).resample("ME").last().dropna()
        comp = sum(np.sign(m.pct_change(L)) for L in LOOKBACKS)
        pos = int(np.sign(comp.iloc[-1]))
        side = "LONG" if pos > 0 else ("SHORT" if pos < 0 else "FLAT")
        print(f"  {a:7s}: comp={comp.iloc[-1]:+.0f}/4 → {side}  (asof {m.index[-1].date()})")


if __name__ == "__main__":
    main()
