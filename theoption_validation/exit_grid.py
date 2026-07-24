#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エグジット安定性グリッド: 銘柄×エントリー時刻×判定時刻 の勝率/Edge一覧 (2026-07-23)
ザオプションの判定時刻が日によって変動するため、既検証アノマリー周辺の
「どの判定時刻なら優位性が保てるか」を網羅的に出す。HIGH方向のみ。
Edgeは保守側: ペイアウト1.90(BE52.63%) + スプレッド/減衰補正-2.0pp。
1.95倍が取れる判定時刻なら +1.35pp 上乗せして読む。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad')

PAIRS = ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY', 'AUDUSD', 'CHFJPY']
ENTRY_HOURS = range(5, 14)          # JST 5..13
SAME_DAY_J = range(8, 24)           # 当日判定 8..23時
NEXT_DAY_J = range(0, 7)            # 翌日判定 0..6時
BE190, BE195, CORR = 100/1.90, 100/1.95, 2.0
ALPHA_EFF = 0.05/3200

def wilson_low(wins, n, z=1.96):
    if n == 0: return 0.0
    p = wins/n
    d = 1 + z*z/n
    c = p + z*z/(2*n)
    m = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (c-m)/d*100

rows = []
for pair in PAIRS:
    df = pd.read_csv(DATA_DIR / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    df = df.set_index('datetime').sort_index()
    close = df['Close']
    for eh in ENTRY_HOURS:
        entries = df[df.index.hour == eh]['Open']
        if entries.empty: continue
        ed = entries.index.normalize()
        configs = [(jh, False) for jh in SAME_DAY_J if jh > eh] + [(jh, True) for jh in NEXT_DAY_J]
        for jh, nd in configs:
            exit_time = ed + pd.Timedelta(days=1 if nd else 0) + pd.Timedelta(hours=jh)
            exit_bar = exit_time - pd.Timedelta(hours=1)
            valid = exit_bar.isin(close.index) & (exit_time > entries.index)
            if valid.sum() < 100: continue
            e_open = entries[valid].to_numpy()
            e_idx = entries.index[valid]
            x_close = close.loc[exit_bar[valid]].to_numpy()
            win = x_close > e_open
            wd = e_idx.dayofweek
            for scope, m in [('ALL', np.ones(len(win), bool)), ('Mon', wd == 0)]:
                n = int(m.sum())
                if n < 100: continue
                wins = int(win[m].sum())
                wr = wins/n*100
                rows.append(dict(pair=pair, scope=scope, entry_h=eh,
                                 judgment=('翌' if nd else '当') + f'{jh:02d}時',
                                 hold_h=(24 if nd else 0) + jh - eh,
                                 n=n, wr=round(wr, 2),
                                 wilson=round(wilson_low(wins, n), 2),
                                 edge190=round(wr - CORR - BE190, 2),
                                 edge195=round(wr - CORR - BE195, 2),
                                 p=stats.binom.sf(wins-1, n, BE190/100),
                                 bonf3200=stats.binom.sf(wins-1, n, BE190/100) < ALPHA_EFF))
    print(pair, 'done')

g = pd.DataFrame(rows)
g['p'] = g['p'].map(lambda x: f'{x:.2e}')
g.to_csv(OUT / 'theoption_exit_grid.csv', index=False, encoding='utf-8-sig')
print(len(g), 'rows ->', OUT / 'theoption_exit_grid.csv')
