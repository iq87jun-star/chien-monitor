#!/usr/bin/env python3
"""公開ソースから10年データを取得し research/data（または CHIEN_DATA_DIR）に保存する。

出典（docs/26 の方法論と整合）:
  - 日足/多資産: Yahoo Finance（yfinance）。SPX=^GSPC, VIX=^VIX, XAUUSD=GC=F,
    USDJPY=JPY=X, EURJPY=EURJPY=X, GBPJPY=GBPJPY=X。
  - 米2年金利 US2Y: FRED 系列 DGS2（CSV 直 DL、APIキー不要）。
  - 円クロス H1: Dukascopy（dukascopy-python、ベストエフォート）。失敗時は v7 相関を
    日足プロキシで代替（lib/v7_reference）。

使い方（Colab 推奨。ネットワーク必要）:
    export CHIEN_DATA_DIR=/content/drive/MyDrive/chien-monitor/data
    python3 research/fetch_data.py            # 全部
    python3 research/fetch_data.py --no-h1    # 日足のみ（速い）
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data as _data  # noqa: E402

START, END = "2016-01-01", "2025-12-31"

YF_DAILY = {           # 保存名: Yahoo ティッカー
    "SPX": "^GSPC",
    "VIX": "^VIX",
    "XAUUSD": "GC=F",
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
}
H1_PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]


def _out_dir() -> str:
    d = os.environ.get("CHIEN_DATA_DIR") or _data.LOCAL_DEFAULT
    os.makedirs(d, exist_ok=True)
    return d


def _save(df: pd.DataFrame, path: str, label: str):
    df.to_csv(path, index=False)
    print(f"  [OK] {label}: {len(df)} 行 -> {path}  ({df['time'].min().date()}..{df['time'].max().date()})")


# ----------------------------------------------------------------- Yahoo daily
def fetch_yf_daily(out: str):
    import yfinance as yf
    print("== Yahoo 日足 ==")
    for name, tkr in YF_DAILY.items():
        try:
            df = yf.download(tkr, start=START, end=END, interval="1d",
                             auto_adjust=False, progress=False)
            if df is None or len(df) == 0:
                print(f"  [WARN] {name} ({tkr}) 空")
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: "time"})
            df.columns = [str(c).lower() for c in df.columns]
            o = df[["time", "open", "high", "low", "close"]].dropna()
            o["time"] = pd.to_datetime(o["time"], utc=True)
            _save(o, os.path.join(out, f"{name}_d.csv"), name)
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {name} ({tkr}): {type(e).__name__}: {e}")


# ----------------------------------------------------------------- FRED US2Y
def fetch_fred_us2y(out: str):
    print("== FRED US2Y (DGS2) ==")
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2"
           f"&cosd={START}&coed={END}")
    try:
        d = pd.read_csv(url)
        tcol, vcol = d.columns[0], d.columns[1]
        d = d.rename(columns={tcol: "time", vcol: "v"})
        d["time"] = pd.to_datetime(d["time"], utc=True)
        d["v"] = pd.to_numeric(d["v"].replace(".", np.nan), errors="coerce")
        d = d.dropna(subset=["v"]).reset_index(drop=True)
        out_df = pd.DataFrame({"time": d["time"], "open": d["v"], "high": d["v"],
                               "low": d["v"], "close": d["v"]})
        _save(out_df, os.path.join(out, "US2Y_d.csv"), "US2Y")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERR] US2Y: {type(e).__name__}: {e}")


# ----------------------------------------------------------------- Dukascopy H1
def _duka_const(mod, *needles):
    for name in dir(mod):
        up = name.upper()
        if all(n in up for n in needles):
            return getattr(mod, name)
    return None


def fetch_dukascopy_h1(out: str):
    print("== Dukascopy 円クロス H1（ベストエフォート）==")
    try:
        import dukascopy_python
        from dukascopy_python import instruments as inst
    except Exception as e:  # noqa: BLE001
        print(f"  [SKIP] dukascopy-python 未導入: {e}")
        print("        -> pip install dukascopy-python  で導入可。")
        print("        未取得でも v7 相関は日足プロキシで代替されます。")
        return
    interval = _duka_const(dukascopy_python, "HOUR_1") or _duka_const(dukascopy_python, "HOUR")
    side = _duka_const(dukascopy_python, "OFFER_SIDE_BID") or _duka_const(dukascopy_python, "BID")
    needle = {"EURJPY": ("EUR", "JPY"), "GBPJPY": ("GBP", "JPY"), "USDJPY": ("USD", "JPY")}
    start = pd.Timestamp(START, tz="UTC")
    end = pd.Timestamp(END, tz="UTC")
    for name in H1_PAIRS:
        instr = _duka_const(inst, *needle[name])
        if instr is None or interval is None or side is None:
            print(f"  [WARN] {name}: 定数解決できず（API差異）。スキップ。")
            continue
        try:
            df = dukascopy_python.fetch(instr, interval, side, start, end)
            if df is None or len(df) == 0:
                print(f"  [WARN] {name} 空")
                continue
            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            df = df.rename(columns={df.columns[0]: "time"})
            o = df[["time", "open", "high", "low", "close"]].dropna()
            o["time"] = pd.to_datetime(o["time"], utc=True)
            _save(o, os.path.join(out, f"{name}_h1.csv"), f"{name} H1")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {name} H1: {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-h1", action="store_true", help="円クロス H1（Dukascopy）を取得しない")
    args = ap.parse_args()
    out = _out_dir()
    print(f"保存先: {out}\n期間: {START}..{END}\n")
    try:
        import yfinance  # noqa: F401
    except Exception:
        print("[setup] pip install yfinance ...")
        os.system(f"{sys.executable} -m pip -q install yfinance")
    fetch_yf_daily(out)
    fetch_fred_us2y(out)
    if not args.no_h1:
        fetch_dukascopy_h1(out)
    print("\n== events_cb_d.csv (E5用・中銀イベント) ==")
    ev = os.path.join(out, "events_cb_d.csv")
    if os.path.exists(ev):
        print(f"  [OK] 既存: {ev}")
    else:
        print(f"  [TODO] 自動取得せず（日付の捏造を避けるため）。{ev} を手動で用意。")
        print("         列: time,kind  kind∈{FOMC,BOJ}。未用意なら E5 は SKIP されます。")
    print("\n完了。次: python3 research/run_all.py")


if __name__ == "__main__":
    main()
