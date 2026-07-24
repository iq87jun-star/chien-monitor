#!/usr/bin/env python3
"""Binance月次zipをdukascopy_hourlyと同形式のCSV(UTC)に変換"""
import pandas as pd, zipfile, io
from pathlib import Path

SC = Path('/tmp/claude-0/-home-user-chien-monitor/bb965c91-9b36-5899-9568-61e61c2aee05/scratchpad')
ZIPS = SC / 'crypto_zips'
OUT = SC / 'hourly'

for sym in ['BTCUSDT', 'ETHUSDT']:
    frames = []
    for z in sorted(ZIPS.glob(f'{sym}-1h-*.zip')):
        with zipfile.ZipFile(z) as zf:
            name = zf.namelist()[0]
            raw = zf.read(name)
        df = pd.read_csv(io.BytesIO(raw), header=None, usecols=range(6),
                         names=['open_time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        if isinstance(df.iloc[0, 0], str):  # ヘッダ行入りファイル対策
            df = df[df['open_time'].astype(str).str.isdigit()].astype(
                {'open_time': 'int64', 'Open': float, 'High': float, 'Low': float, 'Close': float})
        t = df['open_time'].astype('int64')
        # ms(13桁) と us(16桁) の混在に対応
        unit = t.map(lambda x: 'us' if x > 10**14 else 'ms')
        df['datetime'] = pd.to_datetime(t, unit='ms', errors='coerce')
        us_mask = t > 10**14
        if us_mask.any():
            df.loc[us_mask, 'datetime'] = pd.to_datetime(t[us_mask], unit='us')
        frames.append(df[['datetime', 'Open', 'High', 'Low', 'Close']])
    full = pd.concat(frames).drop_duplicates('datetime').sort_values('datetime')
    full['datetime'] = full['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    full.to_csv(OUT / f'{sym}_hourly.csv', index=False)
    print(sym, len(full), full['datetime'].iloc[0], '->', full['datetime'].iloc[-1])
