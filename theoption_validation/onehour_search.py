#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1時間後判定(1.90倍)の事前登録探索 (2026-07-24)
エントリー=時間足Open、判定=同バーClose(=1時間後)。BE=52.63%、補正-2.0pp。

枠組みA (ブラインド探索): 11ペア×24時刻×(Mon-Fri+ALL)×H/L + BTC/ETH×24×(Mon-Sun+ALL)×H/L
  M = 11*24*6*2 + 2*24*8*2 = 3168 + 768 = 3936, α = 0.05/3936 = 1.27e-05
  ゲート: G1 Bonferroni → G2 Wilson>BE → G4半期 → G5年抜き → G3順列(曜日型)
枠組みB (確認試験): 確立済みアノマリーが予測する16セル, α = 0.05/16
  EURGBP 7/8/9/10時H, USDCHF 7/8/9/10時H, 月曜7時H(GBPJPY/AUDJPY/GBPUSD/NZDJPY/CADJPY/EURJPY),
  EURGBP 22/23時L
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
DATA = SCRATCH/'hourly'
START = pd.Timestamp('2016-01-01')
CUTOFF = pd.Timestamp('2026-05-24')
FX = ['EURGBP','USDCHF','GBPJPY','AUDJPY','GBPUSD','NZDJPY','CADJPY','EURJPY','AUDUSD','CHFJPY','EURAUD']
CRYPTO = ['BTCUSDT','ETHUSDT']
BE = 100/1.90
CORR = 2.0
M = 11*24*6*2 + 2*24*8*2
ALPHA = 0.05/M
WD = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

def wilson_low(w, n, z=1.96):
    p = w/n; d = 1+z*z/n; c = p+z*z/(2*n)
    m = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (c-m)/d*100

def perm_p(win, mask, observed_wr, n_shifts=200):
    n = len(win)
    shifts = np.unique(np.linspace(1, n-1, n_shifts).astype(int))
    null = np.array([np.roll(win, k)[mask].mean()*100 for k in shifts])
    return (1 + (null >= observed_wr).sum())/(1+len(shifts))

def load(sym):
    df = pd.read_csv(DATA/f'{sym}_hourly.csv')
    if 'Volume' in df and sym in FX:
        df = df[df['Volume'] > 0]
    df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
    df = df[(df['datetime'] >= START) & (df['datetime'] < CUTOFF)]
    return df.set_index('datetime').sort_index()

cands, finals = [], []
for sym in FX + CRYPTO:
    df = load(sym)
    nscope = 8 if sym in CRYPTO else 6
    for eh in range(24):
        bars = df[df.index.hour == eh]
        if len(bars) < 200: continue
        win_high = (bars['Close'].to_numpy() > bars['Open'].to_numpy())
        wd = bars.index.dayofweek.to_numpy()
        yr = bars.index.year.to_numpy()
        mid = bars.index[len(bars)//2]
        half2 = np.asarray(bars.index > mid)
        scopes = list(range(nscope-1)) + ['ALL']
        for scope in scopes:
            mask = np.ones(len(bars), bool) if scope == 'ALL' else (wd == scope)
            n = int(mask.sum())
            if n < 200: continue
            for direction, w in [('HIGH', win_high), ('LOW', ~win_high)]:
                wins = int(w[mask].sum())
                wr = wins/n*100
                row = dict(sym=sym, entry_h=eh, scope=scope if scope=='ALL' else WD[scope],
                           direction=direction, n=n, wr=round(wr,2),
                           edge_adj=round(wr-CORR-BE,2), wilson=round(wilson_low(wins,n),2),
                           p=stats.binom.sf(wins-1, n, BE/100))
                cands.append(row)
                if row['p'] >= ALPHA or row['wilson'] <= BE: continue
                h1 = w[mask & ~half2]; h2 = w[mask & half2]
                e1 = h1.mean()*100-CORR-BE; e2 = h2.mean()*100-CORR-BE
                if e1 <= 0 or e2 <= 0: continue
                jk = min(w[mask & (yr != y)].mean()*100-CORR-BE for y in np.unique(yr[mask]))
                if jk <= 0: continue
                pp = None if scope == 'ALL' else perm_p(w.astype(float), mask, wr)
                finals.append({**row, 'h1_edge':round(e1,2), 'h2_edge':round(e2,2),
                               'jk_min':round(jk,2), 'perm_p':pp,
                               'grade':'STRONG' if (pp is None or pp < 0.05) else 'LEAD'})
    print(sym, 'done', flush=True)

ac = pd.DataFrame(cands)
ac.to_csv(SCRATCH/'onehour_all_candidates.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals)
if len(f): f = f.sort_values('edge_adj', ascending=False)
f.to_csv(SCRATCH/'onehour_final.csv', index=False, encoding='utf-8-sig')
print(f'\n[枠組みA] α={ALPHA:.2e} 探索{len(ac)} 合格{len(f)}')
if len(f): print(f.to_string(index=False))
print('\n未補正p上位15:')
print(ac.sort_values('p').head(15).to_string(index=False))

# ---- 枠組みB: 確認試験 (16セル, α=0.05/16) ----
CONF = ([('EURGBP', h, 'ALL', 'HIGH') for h in [7,8,9,10]] +
        [('USDCHF', h, 'ALL', 'HIGH') for h in [7,8,9,10]] +
        [(p, 7, 'Mon', 'HIGH') for p in ['GBPJPY','AUDJPY','GBPUSD','NZDJPY','CADJPY','EURJPY']] +
        [('EURGBP', h, 'ALL', 'LOW') for h in [22,23]])
AB = 0.05/len(CONF)
print(f'\n[枠組みB] 確認試験 {len(CONF)}セル α={AB:.4f}')
rows = []
for sym, eh, scope, direction in CONF:
    r = ac[(ac['sym']==sym)&(ac['entry_h']==eh)&(ac['scope']==scope)&(ac['direction']==direction)]
    if len(r) == 0: continue
    r = r.iloc[0].to_dict()
    r['pass'] = (r['p'] < AB) and (r['edge_adj'] > 0)
    rows.append(r)
cf = pd.DataFrame(rows)
print(cf[['sym','entry_h','scope','direction','n','wr','edge_adj','p','pass']].to_string(index=False))
cf.to_csv(SCRATCH/'onehour_confirmatory.csv', index=False, encoding='utf-8-sig')
