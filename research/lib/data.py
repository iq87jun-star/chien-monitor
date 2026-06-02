"""データローダ。Drive / ローカルを自動解決する。

データスキーマ（このスキーマに合わせて CSV を置く / 生成すること）:
  research/data/<SYMBOL>_h1.csv  … FX H1。列: time, open, high, low, close[, spread]
                                     time は UTC。spread は pip 単位の往復スプレッド（任意）。
  research/data/<SYMBOL>_d.csv   … 日足/多資産。列: time, open, high, low, close
                                     SYMBOL 例: XAUUSD, SPX, NDX, US2Y, US10Y, VIX, USDJPY ...

データ置き場の解決順:
  1. 環境変数 CHIEN_DATA_DIR が指すディレクトリ
  2. /content/drive/MyDrive/chien-monitor/data （Colab で Drive マウント時）
  3. research/data （ローカル。短期/一部のみ。拘束力ある10年検定には不可）
"""
import os
import pandas as pd

DRIVE_DEFAULT = "/content/drive/MyDrive/chien-monitor/data"
LOCAL_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)


def data_dir() -> str:
    env = os.environ.get("CHIEN_DATA_DIR")
    if env and os.path.isdir(env):
        return env
    if os.path.isdir(DRIVE_DEFAULT):
        return DRIVE_DEFAULT
    return LOCAL_DEFAULT


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"データ無し: {path}\n  -> CHIEN_DATA_DIR を設定するか research/data に CSV を置く。"
        )
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ("time", "date", "datetime") if c in df.columns), df.columns[0])
    df = df.rename(columns={tcol: "time"})
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return df


def load_h1(symbol: str) -> pd.DataFrame:
    """FX H1 を time インデックスで返す。"""
    df = _read_csv(os.path.join(data_dir(), f"{symbol}_h1.csv"))
    return df.set_index("time")


def load_daily(symbol: str) -> pd.DataFrame:
    """日足/多資産を time インデックスで返す。"""
    df = _read_csv(os.path.join(data_dir(), f"{symbol}_d.csv"))
    return df.set_index("time")


def available(symbol: str, freq: str = "h1") -> bool:
    return os.path.exists(os.path.join(data_dir(), f"{symbol}_{freq}.csv"))
