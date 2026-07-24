#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOLD(XAUUSD)ミッド探索 (2026-07-24) — M=1,440 独立登録
BIDアーティファクト発見を受け、探索の測定基盤をミッド (BID+ASK)/2 に置き換えて
主要ファミリーを一括再探索する。BIDが隠していたエッジの発掘と既存戦略の再監査を兼ねる。

事前登録: 11ペア × エントリー0..23時JST × 判定{1h, 当日11時, 当日14時, 翌2時, 翌6時}
          × (Mon..Fri + ALL) × HIGH/LOW
M = 1*24*5*6*2 = 15,840  α = 0.05/M = 3.16e-06
ペイアウト: 1h/当日11時=1.90 (BE52.63), 当日14時/翌2時/翌6時=1.95 (BE51.28)
補正: -2.0pp。ゲート: G1 Bonferroni → G2 Wilson>BE → G4半期 → G5年抜き → G3順列(曜日型)
OOS: 2026-05-24以降のミッドで参考表示
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
BIDD = SCRATCH/'hourly'; ASKD = SCRATCH/'hourly_ask'
START = pd.Timestamp('2016-01-01'); CUTOFF = pd.Timestamp('2026-05-24')
PAIRS = ['XAUUSD']
M = 1*24*5*6*2
ALPHA = 0.05/M
CORRH = 2.0
WDN = ['Mon','Tue','Wed','Thu','Fri']
JUDGES = [('1h', None, 1.90), ('当11', ('same',11), 1.90), ('当14', ('same',14), 1.95),
          ('翌2', ('next',2), 1.95), ('翌6', ('next',6), 1.95)]

def wilson_low(w, n, z=1.96):
    p = w/n; d = 1+z*z/n; c = p+z*z/(2*n)
    m = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (c-m)/d*100

def perm_p(win, mask, observed_wr, n_shifts=200):
    n = len(win)
    shifts = np.unique(np.linspace(1, n-1, n_shifts).astype(int))
    null = np.array([np.roll(win, k)[mask].mean()*100 for k in shifts])
    return (1 + (null >= observed_wr).sum())/(1+len(shifts))

def load_mid(pair):
    b = pd.read_csv(BIDD/f'{pair}_hourly.csv'); b = b[b['Volume'] > 0]
    a = pd.read_csv(ASKD/f'{pair}_hourly.csv')
    for d in (b, a):
        d['datetime'] = pd.to_datetime(d['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
    b = b.set_index('datetime').sort_index(); a = a.set_index('datetime').sort_index()
    ix = b.index.intersection(a.index)
    return pd.DataFrame({'Open': (b['Open'].loc[ix]+a['Open'].loc[ix])/2,
                         'Close': (b['Close'].loc[ix]+a['Close'].loc[ix])/2})

cands, finals = [], []
for pair in PAIRS:
    full = load_mid(pair)
    df = full[(full.index >= START) & (full.index < CUTOFF)]
    for eh in range(24):
        bars = df[df.index.hour == eh]
        if len(bars) < 200: continue
        wd = bars.index.dayofweek.to_numpy()
        yr = bars.index.year.to_numpy()
        mid_t = bars.index[len(bars)//2]
        half2 = np.asarray(bars.index > mid_t)
        for jname, jspec, payout in JUDGES:
            BE = 100/payout
            if jspec is None:
                win_high = bars['Close'].to_numpy() > bars['Open'].to_numpy()
                valid = np.ones(len(bars), bool)
            else:
                kind, jh = jspec
                if kind == 'same' and eh >= jh: continue
                xt = bars.index.normalize() + pd.Timedelta(days=(1 if kind=='next' else 0), hours=jh) - pd.Timedelta(hours=1)
                valid = np.asarray(xt.isin(df.index)) & np.asarray((xt + pd.Timedelta(hours=1)) > bars.index)
                if valid.sum() < 200: continue
                win_high = np.zeros(len(bars), bool)
                win_high[valid] = df['Close'].loc[xt[valid]].to_numpy() > bars['Open'].to_numpy()[valid]
            for scope in range(6):
                mask = valid & (np.ones(len(bars), bool) if scope == 5 else (wd == scope))
                n = int(mask.sum())
                if n < 200: continue
                for direction in ('HIGH','LOW'):
                    w = win_high if direction == 'HIGH' else ~win_high
                    wins = int(w[mask].sum())
                    wr = wins/n*100
                    row = dict(pair=pair, entry_h=eh, judge=jname,
                               scope='ALL' if scope == 5 else WDN[scope], direction=direction,
                               n=n, wr=round(wr,2), edge_adj=round(wr-CORRH-BE,2),
                               wilson=round(wilson_low(wins,n),2),
                               p=stats.binom.sf(wins-1, n, BE/100), payout=payout)
                    cands.append(row)
                    if row['p'] >= ALPHA or row['wilson'] <= BE: continue
                    h1 = w[mask & ~half2]; h2 = w[mask & half2]
                    e1 = h1.mean()*100-CORRH-BE; e2 = h2.mean()*100-CORRH-BE
                    if e1 <= 0 or e2 <= 0: continue
                    jk = min(w[mask & (yr != y)].mean()*100-CORRH-BE for y in np.unique(yr[mask]))
                    if jk <= 0: continue
                    pp = None if scope == 5 else perm_p(w.astype(float), mask & valid, wr)
                    # OOS
                    oosdf = full[full.index >= CUTOFF]
                    ob = oosdf[oosdf.index.hour == eh]
                    if jspec is None:
                        ow = ob['Close'].to_numpy() > ob['Open'].to_numpy(); ov = np.ones(len(ob), bool)
                    else:
                        kind, jh = jspec
                        oxt = ob.index.normalize() + pd.Timedelta(days=(1 if kind=='next' else 0), hours=jh) - pd.Timedelta(hours=1)
                        ov = np.asarray(oxt.isin(oosdf.index)) & np.asarray((oxt + pd.Timedelta(hours=1)) > ob.index)
                        ow = np.zeros(len(ob), bool)
                        ow[ov] = oosdf['Close'].loc[oxt[ov]].to_numpy() > ob['Open'].to_numpy()[ov]
                    if direction == 'LOW': ow = ~ow
                    om = ov & (np.ones(len(ob), bool) if scope == 5 else (ob.index.dayofweek == scope))
                    o_n = int(om.sum()); o_wr = ow[om].mean()*100 if o_n else np.nan
                    finals.append({**row, 'h1_edge':round(e1,2), 'h2_edge':round(e2,2),
                                   'jk_min':round(jk,2), 'perm_p':pp,
                                   'grade':'STRONG' if (pp is None or pp < 0.05) else 'LEAD',
                                   'oos_n':o_n, 'oos_wr':round(o_wr,1) if o_n else None})
    print(pair, 'done', flush=True)

ac = pd.DataFrame(cands)
ac.to_csv(SCRATCH/'gold_all.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals)
if len(f): f = f.sort_values('edge_adj', ascending=False)
f.to_csv(SCRATCH/'gold_final.csv', index=False, encoding='utf-8-sig')
print(f'\nα={ALPHA:.2e} 探索{len(ac)} 合格{len(f)}')
if len(f): print(f.to_string(index=False))
