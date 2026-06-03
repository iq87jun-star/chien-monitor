#!/usr/bin/env python3
"""E3 再評価用: Dukascopy から実 H1 を取得（金スポット + 円クロス3本）。
- XAUUSD: BID/ASK 両方 → 価格(BID)と実スプレッド実測。
- EURJPY/GBPJPY/USDJPY: BID（v7 相関の精密版用）。
年次フェッチで保存。research/data に *_h1.csv / XAUUSD_d.csv を書く。
"""
import os
import sys
import pandas as pd
import dukascopy_python as dk
from dukascopy_python import instruments as inst

OUT = os.environ.get("CHIEN_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(OUT, exist_ok=True)
Y0, Y1 = 2016, 2025

JOBS = {
    "XAUUSD": inst.INSTRUMENT_FX_METALS_XAU_USD,
    "EURJPY": inst.INSTRUMENT_FX_CROSSES_EUR_JPY,
    "GBPJPY": inst.INSTRUMENT_FX_CROSSES_GBP_JPY,
    "USDJPY": inst.INSTRUMENT_FX_MAJORS_USD_JPY,
}


def fetch_side(instr, side):
    frames = []
    for y in range(Y0, Y1 + 1):
        s = pd.Timestamp(f"{y}-01-01", tz="UTC")
        e = pd.Timestamp(f"{y}-12-31 23:59", tz="UTC")
        for attempt in range(3):
            try:
                df = dk.fetch(instr, dk.INTERVAL_HOUR_1, side, s, e)
                if df is not None and len(df):
                    frames.append(df)
                print(f"    {y}: {0 if df is None else len(df)} rows", flush=True)
                break
            except Exception as ex:  # noqa: BLE001
                print(f"    {y}: retry {attempt+1} ({type(ex).__name__})", flush=True)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out = out[~out.index.duplicated()].sort_index()
    return out


def main():
    for name, instr in JOBS.items():
        print(f"== {name} BID ==", flush=True)
        bid = fetch_side(instr, dk.OFFER_SIDE_BID)
        if bid.empty:
            print(f"  [WARN] {name} BID 空"); continue
        b = bid.reset_index()
        b.columns = [str(c).lower() for c in b.columns]
        b = b.rename(columns={b.columns[0]: "time"})
        b[["time", "open", "high", "low", "close"]].to_csv(os.path.join(OUT, f"{name}_h1.csv"), index=False)
        print(f"  [OK] {name}_h1.csv {len(b)} rows -> {OUT}", flush=True)

        if name == "XAUUSD":
            print("== XAUUSD ASK (スプレッド実測用) ==", flush=True)
            ask = fetch_side(instr, dk.OFFER_SIDE_ASK)
            # 日足(BID OHLC)
            bx = b.set_index(pd.to_datetime(b["time"], utc=True))
            daily = bx[["open", "high", "low", "close"]].resample("1D").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            daily = daily.reset_index().rename(columns={"time": "time"})
            daily.columns = ["time", "open", "high", "low", "close"]
            daily.to_csv(os.path.join(OUT, "XAUUSD_d.csv"), index=False)
            print(f"  [OK] XAUUSD_d.csv {len(daily)} rows", flush=True)
            if not ask.empty:
                a = ask.reset_index(); a.columns = [str(c).lower() for c in a.columns]
                a = a.rename(columns={a.columns[0]: "time"})
                m = pd.merge(b[["time", "close"]], a[["time", "close"]], on="time", suffixes=("_bid", "_ask"))
                sp = (m["close_ask"] - m["close_bid"])
                med_abs = float(sp.median())
                med_frac = float((sp / m["close_bid"]).median())
                with open(os.path.join(OUT, "XAUUSD_spread.txt"), "w") as f:
                    f.write(f"median_abs_usd={med_abs}\nmedian_frac={med_frac}\n")
                print(f"  [OK] 金スプレッド中央値: {med_abs:.3f} USD = {med_frac*1e4:.2f} bp (片道) -> XAUUSD_spread.txt", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
