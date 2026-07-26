#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月曜朝の分足検証: EURJPY/GBPJPY/AUDJPY、7:00 JSTエントリー→+5..+60分判定のミッド勝率カーブ。
月曜7:00 JST = 日曜22:00 UTC → 日曜UTCの日次1分足ファイルのみ取得(BID/ASK)。"""
import lzma, struct, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import pandas as pd
import numpy as np

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
MRAW = SCRATCH/'raw_min'; MRAW.mkdir(exist_ok=True)
PAIRS = ['EURJPY','GBPJPY','AUDJPY']
START = pd.Timestamp('2016-01-01'); END = pd.Timestamp('2026-05-24')

sundays = pd.date_range(START, END, freq='W-SUN')
def fetch(args):
    pair, side, d = args
    dst = MRAW/f'{pair}_{side}_{d:%Y%m%d}.bi5'
    if dst.exists() or dst.with_suffix('.missing').exists(): return
    url = f'https://datafeed.dukascopy.com/datafeed/{pair}/{d.year}/{d.month-1:02d}/{d.day:02d}/{side}_candles_min_1.bi5'
    for a in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                dst.write_bytes(r.read())
            return
        except urllib.error.HTTPError as ex:
            if ex.code == 404: dst.with_suffix('.missing').touch(); return
            time.sleep(2*2**a)
        except Exception:
            time.sleep(2*2**a)
    print('FAIL', pair, side, d.date(), flush=True)

jobs = [(p, s, d) for p in PAIRS for s in ['BID','ASK'] for d in sundays]
print('files to check:', len(jobs), flush=True)
with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, jobs))
print('downloads done', flush=True)

REC = struct.Struct('>IIIIIf')
def day_prices(pair, side, d):
    f = MRAW/f'{pair}_{side}_{d:%Y%m%d}.bi5'
    if not f.exists() or f.stat().st_size == 0: return None
    raw = lzma.decompress(f.read_bytes())
    out = {}
    for i in range(0, len(raw), 24):
        t, o, c, lo, hi, v = REC.unpack_from(raw, i)
        if 75600 <= t <= 84000 and v > 0:   # 21:00-23:20 UTC のみ
            out[t] = (o/1000.0, c/1000.0)
    return out

HORIZONS = [3,5,10,15,20,25,30,40,50,60]
for pair in PAIRS:
    rows = []
    for d in sundays:
        b = day_prices(pair,'BID',d); a = day_prices(pair,'ASK',d)
        if not b or not a: continue
        t0 = 79200  # 22:00:00 UTC = 7:00 JST
        if t0 not in b or t0 not in a: continue
        entry = (b[t0][0]+a[t0][0])/2
        rec = {'date': d}
        for h in HORIZONS:
            tj = t0 + h*60 - 60  # 判定時刻の1分前バーのclose
            if tj in b and tj in a:
                rec[h] = ((b[tj][1]+a[tj][1])/2) > entry
        rows.append(rec)
    df = pd.DataFrame(rows)
    print(f'\n== {pair} 月曜7:00エントリーHIGH (n={len(df)}) ==')
    print(' 判定   n    WR    Edge(1.85) Edge(1.90) 前半  後半')
    for h in HORIZONS:
        s = df[h].dropna()
        n = len(s); wr = s.mean()*100
        mid_i = n//2
        h1 = s.iloc[:mid_i].mean()*100; h2 = s.iloc[mid_i:].mean()*100
        e185 = wr-2-100/1.85; e190 = wr-2-100/1.90
        print(f'+{h:3d}分 {n:4d} {wr:6.2f} {e185:+8.2f} {e190:+8.2f} {h1:6.2f} {h2:6.2f}')
