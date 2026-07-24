#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mid監査フォローアップ (2026-07-24)

A. 採用10戦略のmid判定OOS(5/26-7/23): bidフォワードの見かけとmid実勢の乖離確認
B. 朝ドリフト救済診断: EURGBP/USDCHF, エントリー7-10時×判定11-14時(ALL, HIGH)のbid/mid比較
   → スプレッド正常化後のエントリーで実体ドリフトが残るか
C. 夜間LOW診断: EURGBP 22/23時エントリー×判定翌3-6時のmid WR
   → 判定を翌6:00(ロールオーバー内)から翌4:00等(クリーン)へ移した場合の実体
D. EURAUD 10時LOW×判定翌3-6時のmid WR
"""
import pandas as pd
import numpy as np
from pathlib import Path

SP = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')
WD = dict(Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)


def load_mid(pair):
    b = pd.read_csv(SP / 'hourly' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    a = pd.read_csv(SP / 'hourly_ask' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    m = b.merge(a, on='datetime', suffixes=('_b', '_a'))
    for c in ['Open', 'Close']:
        m[c] = (m[f'{c}_b'] + m[f'{c}_a']) / 2
    m['datetime'] = m['datetime'] + pd.Timedelta(hours=9)
    return m.set_index('datetime').sort_index()


def wr_for(df, po, pc, eh, judge, wds, direc, months_off=()):
    d_off, jh = judge
    e = df[df.index.hour == eh][po]
    if wds is not None:
        e = e[e.index.dayofweek.isin([WD[w] for w in wds])]
    if months_off:
        e = e[~e.index.month.isin(months_off)]
    close = df[pc]
    jt = e.index.normalize() + pd.Timedelta(days=d_off, hours=jh - 1)
    v = jt.isin(close.index)
    e = e[v]
    jc = close.loc[jt[v]].to_numpy()
    win = (jc > e.to_numpy()) if direc == 'H' else (jc < e.to_numpy())
    return pd.Series(win, index=e.index)


MENU = [
    ('EURGBP_D_7-11H',   'EURGBP', None,               7, (0, 11), 'H', ()),
    ('GBPJPY_Mon_7-14H', 'GBPJPY', ['Mon'],            7, (0, 14), 'H', ()),
    ('AUDJPY_Mon_7-n2H', 'AUDJPY', ['Mon'],            7, (1, 2),  'H', ()),
    ('GBPUSD_Mon_7-14H', 'GBPUSD', ['Mon'],            7, (0, 14), 'H', ()),
    ('NZDJPY_Mon_7-14H', 'NZDJPY', ['Mon'],            7, (0, 14), 'H', ()),
    ('CADJPY_Mon_7-14H', 'CADJPY', ['Mon'],            7, (0, 14), 'H', ()),
    ('EURJPY_Mon_7-n6H', 'EURJPY', ['Mon'],            7, (1, 6),  'H', ()),
    ('USDCHF_D_7-14H',   'USDCHF', None,               7, (0, 14), 'H', ()),
    ('EURGBP_N_23-n6L',  'EURGBP', ['Mon','Tue','Wed','Fri'], 23, (1, 6), 'L', (2, 3, 6, 12)),
    ('EURAUD_D_10-n6L',  'EURAUD', None,              10, (1, 6),  'L', ()),
]

dfs = {p: load_mid(p) for p in
       ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY', 'EURAUD']}

print('=== A. 採用10戦略 mid判定OOS (5/26-7/23) ===')
rows = []
for name, pair, wds, eh, judge, direc, moff in MENU:
    df = dfs[pair]
    o = df[df.index >= CUTOFF]
    wb = wr_for(o, 'Open_b', 'Close_b', eh, judge, wds, direc, moff)
    wm = wr_for(o, 'Open', 'Close', eh, judge, wds, direc, moff)
    rows.append(dict(strategy=name, n=len(wm),
                     oos_wr_bid=round(wb.mean() * 100, 1), oos_wr_mid=round(wm.mean() * 100, 1)))
print(pd.DataFrame(rows).to_string(index=False))

print('\n=== B. 朝ドリフト: エントリー時刻をずらしたmid WR (ALL日, HIGH, IS) ===')
for pair in ['EURGBP', 'USDCHF']:
    df = dfs[pair]
    d = df[df.index < CUTOFF]
    tbl = {}
    for eh in [7, 8, 9, 10]:
        col = {}
        for jh in [11, 12, 13, 14]:
            if jh <= eh:
                continue
            wm = wr_for(d, 'Open', 'Close', eh, (0, jh), None, 'H')
            wb = wr_for(d, 'Open_b', 'Close_b', eh, (0, jh), None, 'H')
            col[f'j{jh}'] = f'{wm.mean()*100:.1f} ({wb.mean()*100:.1f})'
        tbl[f'e{eh}'] = col
    print(f'\n{pair}: mid% (bid%)  BE: 1.90→52.6 / 1.95→51.3, 補正-2pp別途')
    print(pd.DataFrame(tbl).T.to_string())

print('\n=== C. EURGBP夜間LOW: 判定時刻別 mid WR (月火水金, 2/3/6/12月除外, IS) ===')
d = dfs['EURGBP'][dfs['EURGBP'].index < CUTOFF]
for eh in [22, 23]:
    for jh in [3, 4, 5, 6]:
        wm = wr_for(d, 'Open', 'Close', eh, (1, jh), ['Mon','Tue','Wed','Fri'], 'L', (2, 3, 6, 12))
        wb = wr_for(d, 'Open_b', 'Close_b', eh, (1, jh), ['Mon','Tue','Wed','Fri'], 'L', (2, 3, 6, 12))
        print(f'  e{eh}→翌{jh}: mid {wm.mean()*100:.2f}% (bid {wb.mean()*100:.2f}%)  n={len(wm)}')

print('\n=== D. EURAUD 10時LOW: 判定時刻別 mid WR (毎日, IS) ===')
d = dfs['EURAUD'][dfs['EURAUD'].index < CUTOFF]
for jh in [3, 4, 5, 6]:
    wm = wr_for(d, 'Open', 'Close', 10, (1, jh), None, 'L')
    wb = wr_for(d, 'Open_b', 'Close_b', 10, (1, jh), None, 'L')
    print(f'  e10→翌{jh}: mid {wm.mean()*100:.2f}% (bid {wb.mean()*100:.2f}%)  n={len(wm)}')
