#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIDアーティファクト検証: ミッド価格 (bid+ask)/2 で
(1) 1時間ロジックの合格セル、(2) 既存採用ポートフォリオ10戦略、を再計算。
ロールオーバー時間帯のスプレッド統計も出す。"""
import pandas as pd
import numpy as np
from pathlib import Path

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
BID = SCRATCH/'hourly'; ASK = SCRATCH/'hourly_ask'
START = pd.Timestamp('2016-01-01'); CUTOFF = pd.Timestamp('2026-05-24')
BE190, BE195 = 100/1.90, 100/1.95

frames = {}
def load(pair):
    if pair not in frames:
        b = pd.read_csv(BID/f'{pair}_hourly.csv'); b = b[b['Volume'] > 0]
        a = pd.read_csv(ASK/f'{pair}_hourly.csv')
        for d in (b, a):
            d['datetime'] = pd.to_datetime(d['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
        b = b.set_index('datetime').sort_index()
        a = a.set_index('datetime').sort_index()
        ix = b.index.intersection(a.index)
        b = b.loc[ix]; a = a.loc[ix]
        m = pd.DataFrame({'Open': (b['Open']+a['Open'])/2, 'Close': (b['Close']+a['Close'])/2,
                          'spr_open': a['Open']-b['Open'], 'spr_close': a['Close']-b['Close'],
                          'bOpen': b['Open'], 'bClose': b['Close']})
        frames[pair] = m
    return frames[pair]

def wr_cell(pair, eh, scope, direction, mode, jh=None, jkind='bar'):
    """jkind='bar': 1時間(同バーClose). else ('same'/'next', jh)"""
    df = load(pair)
    df = df[(df.index >= START) & (df.index < CUTOFF)]
    bars = df[df.index.hour == eh]
    if jkind == 'bar':
        eo = bars['Open'] if mode=='mid' else bars['bOpen']
        xc = bars['Close'] if mode=='mid' else bars['bClose']
        e_idx = bars.index
        win = xc.to_numpy() > eo.to_numpy()
    else:
        e = bars['Open'] if mode=='mid' else bars['bOpen']
        xt = bars.index.normalize() + pd.Timedelta(days=(1 if jkind=='next' else 0), hours=jh) - pd.Timedelta(hours=1)
        v = xt.isin(df.index) & ((xt + pd.Timedelta(hours=1)) > bars.index)
        e = e[v]; e_idx = e.index
        xc = (df['Close'] if mode=='mid' else df['bClose']).loc[xt[v]]
        win = xc.to_numpy() > e.to_numpy()
    if direction == 'LOW': win = ~win
    m = np.ones(len(e_idx), bool)
    if scope == 'Mon': m = (e_idx.dayofweek == 0)
    return int(m.sum()), win[m].mean()*100

print('== スプレッド統計 (EURGBP, pips) ==')
g = load('EURGBP')
g = g[(g.index >= START) & (g.index < CUTOFF)]
for h in [5,6,7,8,12,23]:
    s = g[g.index.hour == h]['spr_open']*10000
    print(f'{h:2d}時 Openスプレッド: 中央値={s.median():.2f} 平均={s.mean():.2f} P90={s.quantile(0.9):.2f}')

print('\n== 1時間ロジック: BID vs MID ==')
CELLS = [('EURGBP',7,'ALL','HIGH'),('EURAUD',7,'ALL','HIGH'),('EURGBP',5,'ALL','LOW'),
         ('CHFJPY',7,'ALL','HIGH'),('EURAUD',5,'ALL','LOW'),('EURJPY',7,'ALL','HIGH'),
         ('USDCHF',5,'ALL','LOW'),('GBPJPY',7,'ALL','HIGH'),('AUDJPY',6,'Mon','HIGH'),
         ('EURJPY',7,'Mon','HIGH'),('USDCHF',7,'Mon','HIGH'),('CADJPY',7,'Mon','HIGH')]
print(f"{'cell':<28} {'n':>5} {'BID_WR':>7} {'MID_WR':>7} {'差':>6}  BE(1.90)={BE190:.2f}")
for pair, eh, scope, d in CELLS:
    n, wb = wr_cell(pair, eh, scope, d, 'bid')
    _, wm = wr_cell(pair, eh, scope, d, 'mid')
    print(f'{pair} {eh}時 {scope} {d:<4} {n:>6} {wb:7.2f} {wm:7.2f} {wm-wb:+6.2f}')

print('\n== 既存採用ポートフォリオ10戦略: BID vs MID ==')
MENU = [('EURGBP','ALL',7,'same',11,'HIGH',BE190),
        ('GBPJPY','Mon',7,'same',14,'HIGH',BE195),
        ('AUDJPY','Mon',7,'next',2,'HIGH',BE195),
        ('GBPUSD','Mon',7,'same',14,'HIGH',BE195),
        ('NZDJPY','Mon',7,'same',14,'HIGH',BE195),
        ('CADJPY','Mon',7,'same',14,'HIGH',BE195),
        ('EURJPY','Mon',7,'next',6,'HIGH',BE195),
        ('USDCHF','ALL',7,'same',14,'HIGH',BE195),
        ('EURGBP','ALL',23,'next',6,'LOW',BE195),
        ('EURAUD','ALL',10,'next',6,'LOW',BE195)]
print(f"{'strategy':<24} {'n':>5} {'BID_WR':>7} {'MID_WR':>7} {'差':>6} {'MID_Edge(-2pp)':>14}")
for pair, scope, eh, jk, jh, d, be in MENU:
    n, wb = wr_cell(pair, eh, scope, d, 'bid', jh, jk)
    _, wm = wr_cell(pair, eh, scope, d, 'mid', jh, jk)
    print(f'{pair} {scope} {eh}→{jk}{jh}時 {d:<4} {n:>5} {wb:7.2f} {wm:7.2f} {wm-wb:+6.2f} {wm-2-be:+14.2f}')
