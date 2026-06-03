"""
build_v7_weekly.py — v7（月曜JPYクロスLONG多ショット）を H1 から再現し、週次リターンを出力。

これはゲート⑥（新候補の v7 独立性）の相関基準を作るためのもの。前セッションの
v7_weekly_returns.csv が存在しないため、EA と同じルールでデータから再生成する。

v7 ルール（FundedNext_Stellar_EA_v7.mq5 / docs より）:
  対象 EURJPY/GBPJPY/USDJPY、月曜 04/06/08/10 UTC に LONG、24h 後に時間決済。
  週12ショット（3ペア×4時刻）。週次リターン = その週の全ショットの単純平均（等加重）。
  ※相関はスケール不変なので、予算配分の絶対サイズは相関基準には不要。

出力: EDGE_DATA_DIR/v7_weekly_returns.csv  (date, ret)
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data_io import load_h1, DATA_DIR

PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]
ENTRY_HOURS_UTC = [4, 6, 8, 10]
HOLD_HOURS = 24


def shot_returns(sym: str) -> pd.Series:
    """各（月曜・時刻）ショットの24h LONG リターンを、エントリー時刻 index で返す。"""
    h1 = load_h1(sym)
    close = h1["close"]
    # 24h 後の終値（H1 なので 24 バー先だが、欠損/休場に頑健に時刻照合する）
    out = {}
    for t, entry in close.items():
        if t.dayofweek != 0 or t.hour not in ENTRY_HOURS_UTC:  # 0=Monday(UTC)
            continue
        exit_t = t + pd.Timedelta(hours=HOLD_HOURS)
        # exit_t 以上で最初に存在する終値
        future = close[close.index >= exit_t]
        if len(future) == 0:
            continue
        exit_px = future.iloc[0]
        if entry > 0:
            out[t] = exit_px / entry - 1.0
    return pd.Series(out).sort_index()


def main():
    all_shots = []
    for sym in PAIRS:
        s = shot_returns(sym)
        print(f"  {sym}: {len(s)} shots")
        all_shots.append(s)
    shots = pd.concat(all_shots).sort_index()
    if shots.empty:
        raise SystemExit("no v7 shots — JPYクロスH1が DATA_DIR に無い可能性")
    # ISO週（月曜始まり）で等加重平均
    weekly = shots.groupby(pd.Grouper(freq="W-MON")).mean().dropna()
    df = pd.DataFrame({"date": weekly.index, "ret": weekly.values})
    path = os.path.join(DATA_DIR, "v7_weekly_returns.csv")
    df.to_csv(path, index=False)
    print(f"[WROTE] {path}  weeks={len(df)}  "
          f"mean={df['ret'].mean():+.5f}  std={df['ret'].std():.5f}  "
          f"{df['date'].min().date()}..{df['date'].max().date()}")


if __name__ == "__main__":
    main()
