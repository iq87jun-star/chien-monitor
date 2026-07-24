#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""採用戦略の再現確認: 新規ダウンロードしたDukascopyデータで既存20戦略+next6のn/WRを再計算し、
zaption-checkブランチの結果CSVと比較する。データ品質ゲート。"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
DATA = SCRATCH/'hourly'
REPO = Path('/home/user/chien-monitor/theoption_validation')

CUTOFF = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp('2026-05-24')
START = pd.Timestamp('2016-01-01')
WD = {'Mon':0,'Tue':1,'Wed':2,'Thu':3,'Fri':4}

frames = {}
def load(pair):
    if pair not in frames:
        df = pd.read_csv(DATA/f'{pair}_hourly.csv')
        df = df[df['Volume'] > 0]
        df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
        frames[pair] = df.set_index('datetime').sort_index()
    return frames[pair]

def trades(pair, entry_h, judgment):
    """judgment: ('same', h) or ('next', h). Returns (entry_index, win_high_bool)."""
    df = load(pair)
    e = df[(df.index.hour == entry_h) & (df.index >= START) & (df.index < CUTOFF)]['Open']
    kind, jh = judgment
    xt = e.index.normalize() + pd.Timedelta(days=(1 if kind == 'next' else 0), hours=jh) - pd.Timedelta(hours=1)
    v = xt.isin(df.index) & ((xt + pd.Timedelta(hours=1)) > e.index)
    e = e[v]
    xclose = df['Close'].loc[xt[v]].to_numpy()
    return e, (xclose > e.to_numpy())

J = {'11:00当日': ('same',11), '14:00当日': ('same',14), '02:00翌日': ('next',2), '06:00翌日': ('next',6)}

ref = pd.read_csv(REPO/'theoption_g3_g5_results.csv', encoding='utf-8-sig')
print(f'== G3/G5 20戦略 (cutoff={CUTOFF.date()}) ==')
bad = 0
for _, r in ref.iterrows():
    e, win = trades(r['pair'], int(r['entry_h']), J[r['judgment']])
    m = e.index.dayofweek == WD[r['weekday']]
    n = int(m.sum()); wr = win[m].mean()*100 if n else 0
    ok = (n == r['ref_n']) and abs(wr - r['ref_wr']) < 0.05
    if not ok: bad += 1
    print(f"{r['pair']} {r['weekday']} {r['entry_h']}時 {r['judgment']}: n={n} (ref {r['ref_n']}) "
          f"WR={wr:.2f} (ref {r['ref_wr']}) {'OK' if ok else '** MISMATCH **'}")

nx = pd.read_csv(REPO/'next6_final.csv', encoding='utf-8-sig')
print('\n== next6 (翌06:00判定) ==')
for _, r in nx.iterrows():
    e, win = trades(r['pair'], int(r['entry_h']), ('next',6))
    m = np.ones(len(e), bool) if r['scope'] == 'ALL' else (e.index.dayofweek == WD[r['scope']])
    w = win if r['direction'] == 'HIGH' else ~win
    n = int(m.sum()); wr = w[m].mean()*100 if n else 0
    ok = (n == r['n']) and abs(wr - r['wr']) < 0.05
    if not ok: bad += 1
    print(f"{r['pair']} {r['scope']} {r['entry_h']}時 {r['direction']}: n={n} (ref {r['n']}) "
          f"WR={wr:.2f} (ref {r['wr']}) {'OK' if ok else '** MISMATCH **'}")

print(f'\nmismatches: {bad}')
