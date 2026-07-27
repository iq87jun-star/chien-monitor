#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仲値(10:00 JST fix)検証: USDJPY時間足スクリーン + ゴトー日分足ピンポイント窓。
事前登録セル: ゴトー日USDJPY 9:00/9:15/9:30→9:55判定HIGH、9:30→10:00HIGH、10:00→10:30LOW (M=5, α=0.01)"""
import lzma, struct, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import pandas as pd
import numpy as np
from scipy import stats

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
RAWB = SCRATCH/'raw_bi5'; RAWA = SCRATCH/'raw_ask'; MRAW = SCRATCH/'raw_min'
START = pd.Timestamp('2016-01-01'); CUTOFF = pd.Timestamp('2026-05-24')
REC = struct.Struct('>IIIIIf')

def fetch(url, dst):
    if dst.exists() or dst.with_suffix('.missing').exists(): return
    for a in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                dst.write_bytes(r.read())
            return
        except urllib.error.HTTPError as ex:
            if ex.code == 404: dst.with_suffix('.missing').touch(); return
            time.sleep(2*2**a)
        except Exception: time.sleep(2*2**a)
    print('FAIL', dst.name, flush=True)

# ---- USDJPY hourly BID/ASK ----
jobs = []
for side, raw in [('BID', RAWB), ('ASK', RAWA)]:
    for y in range(2015, 2027):
        for m in range(12):
            if (y, m) > (2026, 5): continue
            jobs.append((f'https://datafeed.dukascopy.com/datafeed/USDJPY/{y}/{m:02d}/{side}_candles_hour_1.bi5',
                         raw/f'USDJPY_{y}_{m:02d}.bi5'))
with ThreadPoolExecutor(8) as ex:
    list(ex.map(lambda a: fetch(*a), jobs))
print('hourly dl done', flush=True)

def decode_hourly(raw_dir):
    rows = []
    for y in range(2015, 2027):
        for m in range(12):
            if (y, m) > (2026, 5): continue
            f = raw_dir/f'USDJPY_{y}_{m:02d}.bi5'
            if not f.exists() or f.stat().st_size == 0: continue
            raw = lzma.decompress(f.read_bytes())
            base = pd.Timestamp(year=y, month=m+1, day=1)
            for i in range(0, len(raw), 24):
                t, o, c, lo, hi, v = REC.unpack_from(raw, i)
                if v > 0:
                    rows.append((base + pd.Timedelta(seconds=t), o/1000, c/1000))
    df = pd.DataFrame(rows, columns=['datetime','Open','Close']).drop_duplicates('datetime')
    df['datetime'] = df['datetime'] + pd.Timedelta(hours=9)
    return df.set_index('datetime').sort_index()

b = decode_hourly(RAWB); a = decode_hourly(RAWA)
ix = b.index.intersection(a.index)
mid = pd.DataFrame({'Open': (b['Open'].loc[ix]+a['Open'].loc[ix])/2,
                    'Close': (b['Close'].loc[ix]+a['Close'].loc[ix])/2})
mid = mid[(mid.index >= START) & (mid.index < CUTOFF)]

def gotobi_mask(idx):
    out = np.zeros(len(idx), bool)
    for i, ts in enumerate(idx):
        if ts.day % 5 == 0 and ts.day <= 30:
            out[i] = True
        elif ts.dayofweek == 4:
            for ahead in (1, 2):
                nd = ts + pd.Timedelta(days=ahead)
                if nd.day % 5 == 0 and nd.day <= 30 and nd.dayofweek >= 5:
                    out[i] = True
    return out

BE190 = 100/1.90
print('\n== USDJPY 時間足スクリーン (ミッド) ==')
for eh, direction in [(9,'HIGH'), (10,'LOW')]:
    bars = mid[(mid.index.hour == eh) & (mid.index.dayofweek < 5)]
    win = bars['Close'].to_numpy() > bars['Open'].to_numpy()
    if direction == 'LOW': win = ~win
    g = gotobi_mask(bars.index)
    for label, m in [('ゴトー日', g), ('非ゴトー', ~g)]:
        n = int(m.sum()); wr = win[m].mean()*100
        p = stats.binom.sf(int(win[m].sum())-1, n, 0.5)
        print(f'{eh}時{direction} {label}: n={n} WR={wr:.2f}% Edge(1.90)={wr-2-BE190:+.2f} p={p:.4f}')

# ---- ゴトー日の分足 ----
alldays = pd.date_range(START, CUTOFF, freq='B')
gdays = alldays[gotobi_mask(alldays)]
print(f'\nゴトー日数: {len(gdays)}', flush=True)
jobs = []
for side in ['BID','ASK']:
    for d in gdays:
        jobs.append((f'https://datafeed.dukascopy.com/datafeed/USDJPY/{d.year}/{d.month-1:02d}/{d.day:02d}/{side}_candles_min_1.bi5',
                     MRAW/f'USDJPY_{side}_{d:%Y%m%d}.bi5'))
with ThreadPoolExecutor(8) as ex:
    list(ex.map(lambda a: fetch(*a), jobs))
print('minute dl done', flush=True)

def day_prices(d, side):
    f = MRAW/f'USDJPY_{side}_{d:%Y%m%d}.bi5'
    if not f.exists() or f.stat().st_size == 0: return None
    raw = lzma.decompress(f.read_bytes())
    out = {}
    for i in range(0, len(raw), 24):
        t, o, c, lo, hi, v = REC.unpack_from(raw, i)
        if 0 <= t <= 7200 and v > 0:  # 0:00-2:00 UTC = 9:00-11:00 JST
            out[t] = (o/1000, c/1000)
    return out

CELLS = [('9:00→9:55 HIGH', 0, 3300, False), ('9:15→9:55 HIGH', 900, 3300, False),
         ('9:30→9:55 HIGH', 1800, 3300, False), ('9:30→10:00 HIGH', 1800, 3600, False),
         ('10:00→10:30 LOW', 3600, 5400, True)]
res = {name: [] for name, *_ in CELLS}
for d in gdays:
    pb = day_prices(d, 'BID'); pa = day_prices(d, 'ASK')
    if not pb or not pa: continue
    for name, t0, t1, is_low in CELLS:
        tj = t1 - 60
        if t0 in pb and t0 in pa and tj in pb and tj in pa:
            entry = (pb[t0][0]+pa[t0][0])/2
            exitp = (pb[tj][1]+pa[tj][1])/2
            w = exitp > entry
            res[name].append((not w) if is_low else w)

print('\n== ゴトー日 仲値ピンポイント窓 (ミッド, 事前登録5セル α=0.01) ==')
BE185 = 100/1.85
for name, *_ in CELLS:
    s = np.array(res[name])
    n = len(s); wr = s.mean()*100
    p = stats.binom.sf(int(s.sum())-1, n, 0.5)
    mid_i = n//2
    h1 = s[:mid_i].mean()*100; h2 = s[mid_i:].mean()*100
    print(f'{name:<16} n={n:3d} WR={wr:5.2f}% Edge(1.85)={wr-2-BE185:+.2f} Edge(1.90)={wr-2-BE190:+.2f} '
          f'前半={h1:.1f} 後半={h2:.1f} p={p:.2e}')
