#!/usr/bin/env python3
"""ASK hour candles for artifact validation (mid-price check)."""
import lzma, struct, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import pandas as pd

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
RAW = SCRATCH/'raw_ask'; RAW.mkdir(exist_ok=True)
OUT = SCRATCH/'hourly_ask'; OUT.mkdir(exist_ok=True)
PAIRS = ['EURGBP','EURAUD','EURJPY','AUDJPY','USDCHF','GBPJPY','NZDJPY','CADJPY','GBPUSD','CHFJPY','AUDUSD']
DEC = {p: (1000.0 if p.endswith('JPY') else 100000.0) for p in PAIRS}

def fetch(args):
    pair, y, m = args
    dst = RAW/f'{pair}_{y}_{m:02d}.bi5'
    if dst.exists() or (RAW/f'{pair}_{y}_{m:02d}.missing').exists(): return
    url = f'https://datafeed.dukascopy.com/datafeed/{pair}/{y}/{m:02d}/ASK_candles_hour_1.bi5'
    for a in range(7):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                dst.write_bytes(r.read())
            return
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                (RAW/f'{pair}_{y}_{m:02d}.missing').touch(); return
            time.sleep(2*2**a)
        except Exception:
            time.sleep(2*2**a)
    print('FAIL', pair, y, m, flush=True)

jobs = [(p, y, m) for p in PAIRS for y in range(2015, 2027) for m in range(12) if (y, m) <= (2026, 5)]
with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, jobs))
print('downloads done', flush=True)

REC = struct.Struct('>IIIIIf')
for pair in PAIRS:
    rows = []
    dec = DEC[pair]
    for y in range(2015, 2027):
        for m in range(12):
            if (y, m) > (2026, 5): continue
            f = RAW/f'{pair}_{y}_{m:02d}.bi5'
            if not f.exists() or f.stat().st_size == 0: continue
            raw = lzma.decompress(f.read_bytes())
            base = pd.Timestamp(year=y, month=m+1, day=1)
            for i in range(0, len(raw), 24):
                t, o, c, lo, hi, v = REC.unpack_from(raw, i)
                rows.append((base + pd.Timedelta(seconds=t), o/dec, hi/dec, lo/dec, c/dec, v))
    df = pd.DataFrame(rows, columns=['datetime','Open','High','Low','Close','Volume'])
    df = df.drop_duplicates('datetime').sort_values('datetime')
    df.to_csv(OUT/f'{pair}_hourly.csv', index=False)
    print(pair, len(df), flush=True)
