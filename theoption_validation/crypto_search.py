#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC/ETH 事前登録エントリー探索 (2026-07-24)
前セッション裁定「残る拡張はBTC/ETHのデータ調達のみ」を受けた新市場・新データの探索。
FX既存ファミリーと同一の段階ゲートを適用。

事前登録した探索空間 (M = 2×24×8×2 = 768, α = 0.05/768 = 6.51e-05):
  2銘柄(BTCUSDT/ETHUSDT) × エントリー0..23時JST × (Mon..Sun + ALL) × HIGH/LOW
  判定: 翌日06:00 JST (判定バー = 翌日05:00足の終値)。クリプトは週末も判定可能。
段階ゲート (FX時と同一):
  G1 Bonferroni: binom p < 0.05/768
  G2 Wilson95%下限 > BE
  G4 サブサンプル: 前半/後半の両方で補正後Edge > 0
  G5 年抜きJackknife: どの1年を除外しても補正後Edge > 0
  G3 順列検定: 曜日マスク循環シフト200本 perm_p < 0.05 (曜日型のみ)
補正: スプレッド/減衰 -2.0pp。ペイアウトは保守的に1.90 (BE=52.63%) — クリプトの実ペイアウト未確認のため。
データ: Binance 1h klines 2017-08〜2026-05-23 (探索期間をFXと同じ終端で切り、6-7月はOOSに温存)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
DATA = SCRATCH/'hourly'
CUTOFF = pd.Timestamp('2026-05-24')
SYMS = ['BTCUSDT','ETHUSDT']
BE = 100/1.90
CORR = 2.0
M = 2*24*8*2
ALPHA = 0.05/M
WD_NAMES = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

def wilson_low(w, n, z=1.96):
    p = w/n; d = 1+z*z/n; c = p+z*z/(2*n)
    m = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (c-m)/d*100

def perm_p(win, mask, observed_wr, n_shifts=200):
    n = len(win)
    shifts = np.unique(np.linspace(1, n-1, n_shifts).astype(int))
    null = np.array([np.roll(win, k)[mask].mean()*100 for k in shifts])
    return (1 + (null >= observed_wr).sum())/(1+len(shifts))

cands, finals = [], []
for sym in SYMS:
    df = pd.read_csv(DATA/f'{sym}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601') + pd.Timedelta(hours=9)  # UTC→JST
    df = df[df['datetime'] < CUTOFF].set_index('datetime').sort_index()
    close = df['Close']
    for eh in range(24):
        e = df[df.index.hour == eh]['Open']
        xt = e.index.normalize() + pd.Timedelta(days=1, hours=6) - pd.Timedelta(hours=1)
        v = xt.isin(close.index) & ((xt + pd.Timedelta(hours=1)) > e.index)
        e = e[v]
        win_high = (close.loc[xt[v]].to_numpy() > e.to_numpy())
        wd = e.index.dayofweek.to_numpy()
        yr = e.index.year.to_numpy()
        mid = e.index[len(e)//2]
        half2 = np.asarray(e.index > mid)
        for scope in range(8):  # 0-6=Mon..Sun, 7=ALL
            mask = np.ones(len(e), bool) if scope == 7 else (wd == scope)
            n = int(mask.sum())
            if n < 200: continue
            for direction, w in [('HIGH', win_high), ('LOW', ~win_high)]:
                wins = int(w[mask].sum())
                wr = wins/n*100
                edge = wr - CORR - BE
                p = stats.binom.sf(wins-1, n, BE/100)
                row = dict(sym=sym, entry_h=eh, scope='ALL' if scope == 7 else WD_NAMES[scope],
                           direction=direction, n=n, wr=round(wr,2), edge_adj=round(edge,2),
                           wilson=round(wilson_low(wins,n),2), p=p)
                cands.append(row)
                if p >= ALPHA or row['wilson'] <= BE: continue
                h1 = w[mask & ~half2]; h2 = w[mask & half2]
                e1 = h1.mean()*100-CORR-BE; e2 = h2.mean()*100-CORR-BE
                if e1 <= 0 or e2 <= 0:
                    finals.append({**row, 'h1_edge': round(e1,2), 'h2_edge': round(e2,2),
                                   'jk_min': None, 'perm_p': None, 'grade': 'FAIL_G4'})
                    continue
                jk = min(w[mask & (yr != y)].mean()*100-CORR-BE for y in np.unique(yr[mask]))
                if jk <= 0:
                    finals.append({**row, 'h1_edge': round(e1,2), 'h2_edge': round(e2,2),
                                   'jk_min': round(jk,2), 'perm_p': None, 'grade': 'FAIL_G5'})
                    continue
                pp = None
                if scope != 7:
                    pp = perm_p(w.astype(float), mask, wr)
                finals.append({**row, 'h1_edge': round(e1,2), 'h2_edge': round(e2,2),
                               'jk_min': round(jk,2), 'perm_p': pp,
                               'grade': ('STRONG' if (pp is None or pp < 0.05) else 'LEAD')})
    print(sym, 'done')

ac = pd.DataFrame(cands)
ac.to_csv(SCRATCH/'crypto_all_candidates.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals)
if len(f): f = f.sort_values('edge_adj', ascending=False)
f.to_csv(SCRATCH/'crypto_final.csv', index=False, encoding='utf-8-sig')
print(f'\nα={ALPHA:.2e}  探索{len(cands)}  G1/G2通過{len(f)}')
if len(f): print(f.to_string(index=False))
print('\n== 参考: p値上位10候補 (未補正) ==')
print(ac.sort_values('p').head(10).to_string(index=False))

# 参考: 上位候補のOOS (2026-05-24以降)
print('\n== OOS 2026-05-24以降 (G1/G2通過のみ) ==')
for _, r in f.iterrows():
    if str(r['grade']).startswith('FAIL'): continue
    sym = r['sym']
    df = pd.read_csv(DATA/f'{sym}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
    df = df[df['datetime'] >= CUTOFF].set_index('datetime').sort_index()
    e = df[df.index.hour == int(r['entry_h'])]['Open']
    xt = e.index.normalize() + pd.Timedelta(days=1, hours=6) - pd.Timedelta(hours=1)
    v = xt.isin(df.index) & ((xt + pd.Timedelta(hours=1)) > e.index)
    e = e[v]
    w = df['Close'].loc[xt[v]].to_numpy() > e.to_numpy()
    if r['direction'] == 'LOW': w = ~w
    if r['scope'] != 'ALL':
        w = w[e.index.dayofweek == WD_NAMES.index(r['scope'])]
    if len(w) == 0: continue
    print(f"{sym} {r['entry_h']}時 {r['scope']} {r['direction']}: OOS n={len(w)} WR={w.mean()*100:.1f}%")
