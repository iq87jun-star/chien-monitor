#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MID価格監査 (2026-07-24): BIDのみのバックテストに含まれる気配アーティファクトの定量化

背景: 1時間判定探索(famC)の合格94本が全てロールオーバー周辺(5-8時JST)に集中し、
かつ「5時LOW」が全ペア一斉に出る(=USDが同時に強く・弱くなる)という価格として
あり得ないパターンを示した。BIDはロールオーバーのスプレッド拡大で下方に歪むため、
ASK取得のうえ mid=(BID+ASK)/2 で再判定し、本物とアーティファクトを切り分ける。
ブローカーのエントリー/判定レートはmid相当のため、midが実運用に忠実なモデル。

出力:
1. 時刻別スプレッド(pips相当, 対終値比): ロールオーバー時間帯の歪み確認
2. famC合格94本の mid再判定(WR_bid vs WR_mid, mid版Bonferroni可否)
3. 採用10戦略の mid再判定(IS): 特に翌06:00判定のLOW系への影響
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SP = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')
WD = dict(Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)
WD_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
PAIRS = ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY',
         'AUDUSD', 'CHFJPY', 'USDJPY', 'EURUSD', 'NZDUSD', 'USDCAD', 'EURAUD', 'GBPAUD']


def load_mid(pair):
    b = pd.read_csv(SP / 'hourly' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    a = pd.read_csv(SP / 'hourly_ask' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    m = b.merge(a, on='datetime', suffixes=('_b', '_a'))
    for c in ['Open', 'High', 'Low', 'Close']:
        m[c] = (m[f'{c}_b'] + m[f'{c}_a']) / 2
    m['spread_close'] = m['Close_a'] - m['Close_b']
    m['datetime'] = m['datetime'] + pd.Timedelta(hours=9)  # JST
    return m.set_index('datetime').sort_index()


def wr_for(df, price_open, price_close, eh, judge, wds, direction, months_off=()):
    d_off, jh = judge
    e = df[df.index.hour == eh][price_open]
    if wds is not None:
        e = e[e.index.dayofweek.isin([WD[w] for w in wds])]
    if months_off:
        e = e[~e.index.month.isin(months_off)]
    close = df[price_close]
    jt = e.index.normalize() + pd.Timedelta(days=d_off, hours=jh - 1)
    v = jt.isin(close.index)
    e = e[v]
    jc = close.loc[jt[v]].to_numpy()
    win = (jc > e.to_numpy()) if direction == 'H' else (jc < e.to_numpy())
    return pd.Series(win, index=e.index)


def main():
    dfs = {p: load_mid(p) for p in PAIRS}

    print('=== 1. 時刻別スプレッド(Close時点, 対価格比bp) ===')
    rows = {}
    for p in ['EURGBP', 'USDCHF', 'AUDJPY', 'EURJPY']:
        d = dfs[p][dfs[p].index < CUTOFF]
        rows[p] = (d['spread_close'] / d['Close'] * 1e4).groupby(d.index.hour).mean().round(2)
    print(pd.DataFrame(rows).to_string())

    print('\n=== 2. famC(1時間判定)合格94本のmid再判定 ===')
    fam = pd.read_csv(SP / 'famC_1h_final.csv')
    BE190 = 100 / 1.90
    out = []
    for _, r in fam.iterrows():
        df = dfs[r['pair']]
        d = df[df.index < CUTOFF]
        wds = None if r['scope'] == 'ALL' else [r['scope']]
        w_mid = wr_for(d, 'Open', 'Close', int(r['entry_h']), (0, int(r['entry_h']) + 1),
                       wds, 'H' if r['direction'] == 'HIGH' else 'L')
        n, wins = len(w_mid), int(w_mid.sum())
        wr_mid = wins / n * 100
        p_mid = stats.binom.sf(wins - 1, n, BE190 / 100)
        out.append(dict(pair=r['pair'], entry_h=r['entry_h'], scope=r['scope'], direction=r['direction'],
                        n=n, wr_bid=r['wr'], wr_mid=round(wr_mid, 2),
                        drop_pp=round(r['wr'] - wr_mid, 2),
                        edge_mid=round(wr_mid - 2.0 - BE190, 2), p_mid=p_mid,
                        mid_bonf=p_mid < 0.05 / 4608))
    o = pd.DataFrame(out).sort_values('edge_mid', ascending=False)
    o.to_csv(SP / 'famC_mid_audit.csv', index=False, encoding='utf-8-sig')
    surv = o[(o['mid_bonf']) & (o['edge_mid'] > 0)]
    print(f'mid再判定でBonferroni+Edge>0を維持: {len(surv)}/{len(o)}本')
    print(surv.to_string(index=False) if len(surv) else '(なし)')
    print('\n時刻別の平均WR低下(bid→mid, pp):')
    print(o.groupby(['entry_h', 'direction'])['drop_pp'].mean().round(2).to_string())

    print('\n=== 3. 採用10戦略のmid再判定(IS) ===')
    MENU = [
        ('EURGBP_D_7-11H',   'EURGBP', None,               7, (0, 11), 'H', 1.90, ()),
        ('GBPJPY_Mon_7-14H', 'GBPJPY', ['Mon'],            7, (0, 14), 'H', 1.95, ()),
        ('AUDJPY_Mon_7-n2H', 'AUDJPY', ['Mon'],            7, (1, 2),  'H', 1.95, ()),
        ('GBPUSD_Mon_7-14H', 'GBPUSD', ['Mon'],            7, (0, 14), 'H', 1.95, ()),
        ('NZDJPY_Mon_7-14H', 'NZDJPY', ['Mon'],            7, (0, 14), 'H', 1.95, ()),
        ('CADJPY_Mon_7-14H', 'CADJPY', ['Mon'],            7, (0, 14), 'H', 1.95, ()),
        ('EURJPY_Mon_7-n6H', 'EURJPY', ['Mon'],            7, (1, 6),  'H', 1.95, ()),
        ('USDCHF_D_7-14H',   'USDCHF', None,               7, (0, 14), 'H', 1.95, ()),
        ('EURGBP_N_23-n6L',  'EURGBP', ['Mon','Tue','Wed','Fri'], 23, (1, 6), 'L', 1.95, (2, 3, 6, 12)),
        ('EURAUD_D_10-n6L',  'EURAUD', None,              10, (1, 6),  'L', 1.95, ()),
    ]
    res = []
    for name, pair, wds, eh, judge, direc, payout, moff in MENU:
        df = dfs[pair]
        d = df[df.index < CUTOFF]
        wb = wr_for(d, 'Open_b', 'Close_b', eh, judge, wds, direc, moff)
        wm = wr_for(d, 'Open', 'Close', eh, judge, wds, direc, moff)
        be = 100 / payout
        res.append(dict(strategy=name, n=len(wm),
                        wr_bid=round(wb.mean() * 100, 2), wr_mid=round(wm.mean() * 100, 2),
                        diff_pp=round((wm.mean() - wb.mean()) * 100, 2),
                        edge_mid_corr0=round(wm.mean() * 100 - be, 2),
                        edge_mid_corr2=round(wm.mean() * 100 - 2.0 - be, 2)))
    r = pd.DataFrame(res)
    r.to_csv(SP / 'menu_mid_audit.csv', index=False, encoding='utf-8-sig')
    print(r.to_string(index=False))
    print('\n(edge_mid_corr0=mid判定・補正なしEdge, corr2=従来通り-2pp補正後。'
          'midが実勢に近いため、真のEdgeはこの間にある)')


if __name__ == '__main__':
    main()
