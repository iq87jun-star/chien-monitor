#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翌日06:00判定 専用ロジック探索 (2026-07-24)
ザオプションの判定時刻が翌06:00のみ提供される日が多いため、判定を翌06:00に固定した
戦略ファミリーを新規に事前登録して全数検証する。

探索空間 (M=2160, Bonferroni α=0.05/M):
  10ペア × エントリー6..23時JST × (Mon..Fri + ALL) × HIGH/LOW
判定: エントリー翌日の06:00 JST (判定バー=翌日05:00足の終値)

段階ゲート:
  G1 Bonferroni: binom p < 0.05/2160
  G2 Wilson95%下限 > BE (51.28%, ペイアウト1.95)
  G4 サブサンプル: 前半(2016-2020)/後半(2021-2026)の両方で補正後Edge > 0
  G5 年抜きJackknife: どの1年を除外しても補正後Edge > 0
  G3 順列検定: 曜日マスク循環シフト200本 perm_p < 0.05 (曜日型のみ。ALLはドリフト型として別掲)
補正: スプレッド-1.0pp + 減衰-1.0pp = -2.0pp
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad')
PAIRS = ['EURGBP','USDCHF','GBPJPY','AUDJPY','GBPUSD','NZDJPY','CADJPY','EURJPY','AUDUSD','CHFJPY']
ENTRIES = range(6, 24)
BE = 100/1.95
CORR = 2.0
M = 2160
ALPHA = 0.05/M
WD_NAMES = ['Mon','Tue','Wed','Thu','Fri']

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
for pair in PAIRS:
    df = pd.read_csv(DATA/f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    df = df.set_index('datetime').sort_index()
    close = df['Close']
    for eh in ENTRIES:
        e = df[df.index.hour == eh]['Open']
        xt = e.index.normalize() + pd.Timedelta(days=1, hours=6) - pd.Timedelta(hours=1)
        v = xt.isin(close.index)
        e = e[v]
        win_high = (close.loc[xt[v]].to_numpy() > e.to_numpy())
        wd = e.index.dayofweek.to_numpy()
        yr = e.index.year.to_numpy()
        mid = e.index[len(e)//2]
        half2 = np.asarray(e.index > mid)
        for scope in range(6):  # 0-4=Mon..Fri, 5=ALL
            mask = np.ones(len(e), bool) if scope == 5 else (wd == scope)
            n = int(mask.sum())
            if n < 200: continue
            for direction, w in [('HIGH', win_high), ('LOW', ~win_high)]:
                wins = int(w[mask].sum())
                wr = wins/n*100
                edge = wr - CORR - BE
                p = stats.binom.sf(wins-1, n, BE/100)
                row = dict(pair=pair, entry_h=eh, scope='ALL' if scope == 5 else WD_NAMES[scope],
                           direction=direction, n=n, wr=round(wr,2), edge_adj=round(edge,2),
                           wilson=round(wilson_low(wins,n),2), p=p)
                cands.append(row)
                if p >= ALPHA or row['wilson'] <= BE: continue
                h1 = w[mask & ~half2]; h2 = w[mask & half2]
                e1 = h1.mean()*100-CORR-BE; e2 = h2.mean()*100-CORR-BE
                if e1 <= 0 or e2 <= 0: continue
                jk = min(w[mask & (yr != y)].mean()*100-CORR-BE for y in np.unique(yr[mask]))
                if jk <= 0: continue
                pp = None
                if scope != 5:
                    pp = perm_p(w.astype(float), mask, wr)
                finals.append({**row, 'h1_edge': round(e1,2), 'h2_edge': round(e2,2),
                               'jk_min': round(jk,2), 'perm_p': pp,
                               'grade': ('STRONG' if (pp is None or pp < 0.05) else 'LEAD')})
    print(pair, 'done')

pd.DataFrame(cands).to_csv(OUT/'next6_all_candidates.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals).sort_values('edge_adj', ascending=False)
f.to_csv(OUT/'next6_final.csv', index=False, encoding='utf-8-sig')
print(f'\nα={ALPHA:.2e}  探索{len(cands)}  最終合格{len(f)}')
print(f.to_string(index=False))
