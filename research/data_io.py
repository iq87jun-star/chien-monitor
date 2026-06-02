"""
data_io.py — 10年データのロード（Drive / ローカル両対応）

EDGE_DATA_DIR でデータ置き場を切替（docs §5 / research/data/README.md）:
  Colab : /content/drive/MyDrive/edge_research/data
  ローカル: ./research/data
H1 CSV スキーマ:
  time(UTC ISO8601), open, high, low, close[, bid_close, ask_close, volume]
"""
from __future__ import annotations

import os
import pandas as pd

DATA_DIR = os.environ.get("EDGE_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
# 結果 JSON の出力先（Colab では Drive を指す）。既定はリポジトリの reports/。
REPORTS_DIR = os.environ.get("EDGE_REPORTS_DIR",
                             os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports"))


def report_path(name: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return os.path.join(REPORTS_DIR, name)

# JPY クォートのペアは pip=0.01、その他 FX は 0.0001。指数はコスト表で直接指定。
def pip_size(symbol: str) -> float:
    return 0.01 if symbol.upper().endswith("JPY") else 0.0001


def load_h1(symbol: str, data_dir: str | None = None) -> pd.DataFrame:
    """H1 OHLC を UTC index の DataFrame で返す。"""
    d = data_dir or DATA_DIR
    path = os.path.join(d, f"{symbol}_h1.csv")
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    if "bid_close" not in df.columns:
        df["bid_close"] = df["close"]
    if "ask_close" not in df.columns:
        df["ask_close"] = df["close"]
    return df


def to_daily(h1: pd.DataFrame) -> pd.DataFrame:
    """H1 → 日足（UTC 日境界）。open/high/low/close を集計。"""
    o = h1["open"].resample("1D").first()
    h = h1["high"].resample("1D").max()
    l = h1["low"].resample("1D").min()
    c = h1["close"].resample("1D").last()
    out = pd.concat([o, h, l, c], axis=1, keys=["open", "high", "low", "close"]).dropna()
    return out


def load_v7_weekly(data_dir: str | None = None) -> pd.Series:
    """v7 週次リターン（ゲート⑥の相関基準）。`date,ret` の CSV。"""
    d = data_dir or DATA_DIR
    path = os.path.join(d, "v7_weekly_returns.csv")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    s = pd.Series(df["ret"].values, index=df["date"]).sort_index()
    # 週次（月曜）に正規化
    return s.resample("W-MON").sum()


def load_costs(data_dir: str | None = None) -> pd.DataFrame:
    """costs.csv: symbol, roundtrip_cost_frac, swap_frac_per_night。

    roundtrip_cost_frac = 往復スプレッドの名目比（例 0.00006 = 0.6pip @ 1.0）。
    swap_frac_per_night = 1泊スワップの名目比（符号付き）。E3C はスワップ除外＝0扱い。
    """
    d = data_dir or DATA_DIR
    path = os.path.join(d, "costs.csv")
    df = pd.read_csv(path).set_index("symbol")
    return df


def cost_for(symbol: str, nights: int, costs: pd.DataFrame, include_swap: bool = True) -> float:
    """1トレードの往復コスト（名目比, >=0 をリターンから引く想定で絶対値運用）。"""
    if symbol not in costs.index:
        return 0.0
    row = costs.loc[symbol]
    c = float(row.get("roundtrip_cost_frac", 0.0))
    if include_swap:
        c += abs(float(row.get("swap_frac_per_night", 0.0))) * max(nights, 0)
    return c
