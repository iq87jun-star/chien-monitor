"""
fetch_data.py — Dukascopy から 10年 H1 を取得し、本プロジェクトのCSVスキーマで保存。

スキーマ: time(UTC ISO8601), open, high, low, close, bid_close, ask_close, volume
  OHLC は BID 側（v7 検証が bid/ask スプレッド前提のため）。bid_close/ask_close を併記し、
  往復スプレッドは ask_close - bid_close からも算出可能。

使い方:
  pip install dukascopy-python
  EDGE_DATA_DIR=/content/drive/MyDrive/edge_research/data \
    python3 research/fetch_data.py --start 2016-01-01 --end 2025-12-31
  # 一部だけ: --symbols EURUSD,GBPUSD  /  既存ファイルは既定でスキップ（--force で上書き）
注意: 10年×16銘柄は時間がかかる（数十分〜）。年次チャンク・銘柄ごとに保存し、再開可能。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd

import dukascopy_python as dk
from dukascopy_python import instruments as I

DATA_DIR = os.environ.get("EDGE_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

# 本プロジェクトのシンボル → Dukascopy インストルメント・コード（live で全件確認済み）
SYMBOLS = {
    # FX（定数の値＝"EUR/USD" 等の文字列を格納）
    "EURUSD": I.INSTRUMENT_FX_MAJORS_EUR_USD,
    "GBPUSD": I.INSTRUMENT_FX_MAJORS_GBP_USD,
    "USDJPY": I.INSTRUMENT_FX_MAJORS_USD_JPY,
    "EURJPY": I.INSTRUMENT_FX_CROSSES_EUR_JPY,
    "GBPJPY": I.INSTRUMENT_FX_CROSSES_GBP_JPY,
    "AUDJPY": I.INSTRUMENT_FX_CROSSES_AUD_JPY,
    "CADJPY": I.INSTRUMENT_FX_CROSSES_CAD_JPY,
    "AUDUSD": I.INSTRUMENT_FX_MAJORS_AUD_USD,
    "NZDUSD": I.INSTRUMENT_FX_MAJORS_NZD_USD,
    "USDCHF": I.INSTRUMENT_FX_MAJORS_USD_CHF,
    "USDCAD": I.INSTRUMENT_FX_MAJORS_USD_CAD,
    "USDSEK": I.INSTRUMENT_FX_CROSSES_USD_SEK,
    "USDNOK": I.INSTRUMENT_FX_CROSSES_USD_NOK,
    # 指数（直接コード・live で確認済み）
    "US500":  "USA500.IDX/USD",
    "NAS100": "USATECH.IDX/USD",
    "JP225":  "JPN.IDX/JPY",
}


def _fetch_side(code: str, side: str, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    return dk.fetch(code, dk.INTERVAL_HOUR_1, side, start, end)


def fetch_symbol(sym: str, code: str, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    """BID/ASK を年次チャンクで取得し、本スキーマの DataFrame に整形。"""
    chunks = []
    y = start.year
    while y <= end.year:
        cs = max(start, dt.datetime(y, 1, 1))
        ce = min(end, dt.datetime(y, 12, 31, 23, 59))
        for attempt in range(3):
            try:
                bid = _fetch_side(code, dk.OFFER_SIDE_BID, cs, ce)
                ask = _fetch_side(code, dk.OFFER_SIDE_ASK, cs, ce)
                break
            except Exception as ex:
                if attempt == 2:
                    raise
                print(f"    {sym} {y} retry {attempt+1}: {str(ex)[:60]}")
                time.sleep(2 * (attempt + 1))
        if bid is not None and len(bid):
            df = bid.rename(columns={"close": "close"}).copy()
            df["bid_close"] = bid["close"]
            df["ask_close"] = ask["close"].reindex(bid.index) if ask is not None else bid["close"]
            chunks.append(df)
        print(f"    {sym} {y}: {0 if bid is None else len(bid)} bars")
        y += 1
    if not chunks:
        return pd.DataFrame()
    out = pd.concat(chunks).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    out.index.name = "time"
    return out[["open", "high", "low", "close", "bid_close", "ask_close", "volume"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--symbols", default="", help="カンマ区切り。空=全銘柄")
    ap.add_argument("--force", action="store_true", help="既存CSVも上書き")
    ap.add_argument("--data-dir", default=DATA_DIR)
    args = ap.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    start = dt.datetime.fromisoformat(args.start)
    end = dt.datetime.fromisoformat(args.end)
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or list(SYMBOLS)

    for sym in syms:
        if sym not in SYMBOLS:
            print(f"[SKIP] unknown symbol {sym}"); continue
        path = os.path.join(args.data_dir, f"{sym}_h1.csv")
        if os.path.exists(path) and not args.force:
            print(f"[HAVE] {sym} (exists, skip)"); continue
        print(f"[FETCH] {sym} {args.start}..{args.end}")
        df = fetch_symbol(sym, SYMBOLS[sym], start, end)
        if df.empty:
            print(f"[WARN] {sym}: no data"); continue
        df.to_csv(path)
        print(f"[WROTE] {path}  rows={len(df)}  {df.index.min()}..{df.index.max()}")
    print("DONE.")


if __name__ == "__main__":
    main()
