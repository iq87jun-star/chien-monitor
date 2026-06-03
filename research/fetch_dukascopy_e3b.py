#!/usr/bin/env python3
"""E3 再評価データの続き: XAUUSD日足を既存H1から構築 + 円クロス3本H1 + 金スプレッド推定。"""
import os
import pandas as pd
import dukascopy_python as dk
from dukascopy_python import instruments as inst

OUT = os.environ.get("CHIEN_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
Y0, Y1 = 2016, 2025


def fetch_side(instr, side, y0=Y0, y1=Y1):
    frames = []
    for y in range(y0, y1 + 1):
        s = pd.Timestamp(f"{y}-01-01", tz="UTC"); e = pd.Timestamp(f"{y}-12-31 23:59", tz="UTC")
        for _ in range(3):
            try:
                df = dk.fetch(instr, dk.INTERVAL_HOUR_1, side, s, e)
                if df is not None and len(df):
                    frames.append(df)
                print(f"    {y}: {0 if df is None else len(df)}", flush=True); break
            except Exception as ex:  # noqa: BLE001
                print(f"    {y}: retry ({type(ex).__name__})", flush=True)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames); return out[~out.index.duplicated()].sort_index()


# 1) XAUUSD 日足を既存 BID H1 から
h1 = pd.read_csv(os.path.join(OUT, "XAUUSD_h1.csv"))
h1["time"] = pd.to_datetime(h1["time"], utc=True)
daily = h1.set_index("time")[["open", "high", "low", "close"]].resample("1D").agg(
    {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
daily.columns = ["time", "open", "high", "low", "close"]
daily.to_csv(os.path.join(OUT, "XAUUSD_d.csv"), index=False)
print(f"[OK] XAUUSD_d.csv {len(daily)} rows (Dukascopy spot)", flush=True)

# 2) 円クロス3本 H1 (BID)
for name, instr in (("EURJPY", inst.INSTRUMENT_FX_CROSSES_EUR_JPY),
                    ("GBPJPY", inst.INSTRUMENT_FX_CROSSES_GBP_JPY),
                    ("USDJPY", inst.INSTRUMENT_FX_MAJORS_USD_JPY)):
    print(f"== {name} BID H1 ==", flush=True)
    b = fetch_side(instr, dk.OFFER_SIDE_BID)
    if b.empty:
        print(f"  [WARN] {name} 空"); continue
    b = b.reset_index(); b.columns = [str(c).lower() for c in b.columns]
    b = b.rename(columns={b.columns[0]: "time"})
    b[["time", "open", "high", "low", "close"]].to_csv(os.path.join(OUT, f"{name}_h1.csv"), index=False)
    print(f"  [OK] {name}_h1.csv {len(b)} rows", flush=True)

# 3) 金スプレッド: 2022-2023 サンプルで ASK を取り中央値推定
print("== 金スプレッド推定 (2022-2023 ASK サンプル) ==", flush=True)
ask = fetch_side(inst.INSTRUMENT_FX_METALS_XAU_USD, dk.OFFER_SIDE_ASK, 2022, 2023)
if not ask.empty:
    a = ask.reset_index(); a.columns = [str(c).lower() for c in a.columns]
    a = a.rename(columns={a.columns[0]: "time"})
    a["time"] = pd.to_datetime(a["time"], utc=True)
    m = pd.merge(h1[["time", "close"]], a[["time", "close"]], on="time", suffixes=("_bid", "_ask")).dropna()
    sp = (m["close_ask"] - m["close_bid"])
    med_abs = float(sp.median()); med_frac = float((sp / m["close_bid"]).median())
    with open(os.path.join(OUT, "XAUUSD_spread.txt"), "w") as f:
        f.write(f"median_abs_usd={med_abs}\nmedian_frac={med_frac}\n")
    print(f"  [OK] 金スプレッド中央値 {med_abs:.3f} USD = {med_frac*1e4:.2f}bp 片道", flush=True)
print("DONE", flush=True)
