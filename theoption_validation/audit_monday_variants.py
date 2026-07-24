#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月曜ファミリーのバリアントmid監査 (2026-07-24)

確立済み月曜アノマリー(ファミリー内確認試験, α=0.05/検定数)の範囲で:
- 6時エントリー群(next6のTier1候補): 週明け最初期。bid合格済みだがmid未検証
- 8時エントリー群: ロールオーバー完全終了後のクリーンな執行版が成立するか
判定は {当日14時, 翌6時} ペイアウト1.95(BE51.28%)、補正-2pp。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SP = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')
PAIRS = ['EURJPY', 'GBPJPY', 'CADJPY', 'NZDJPY', 'AUDJPY', 'CHFJPY', 'GBPUSD', 'USDJPY']
BE = 100 / 1.95
TESTS = [(eh, j) for eh in [6, 8] for j in [(0, 14), (1, 6)]]
N_TESTS = len(PAIRS) * len(TESTS)
ALPHA = 0.05 / N_TESTS


def load_mid(pair):
    b = pd.read_csv(SP / 'hourly' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    a = pd.read_csv(SP / 'hourly_ask' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    m = b.merge(a, on='datetime', suffixes=('_b', '_a'))
    for c in ['Open', 'Close']:
        m[c] = (m[f'{c}_b'] + m[f'{c}_a']) / 2
    m['datetime'] = m['datetime'] + pd.Timedelta(hours=9)
    return m.set_index('datetime').sort_index()


rows = []
for pair in PAIRS:
    df = load_mid(pair)
    d = df[df.index < CUTOFF]
    for eh, (doff, jh) in TESTS:
        e = d[(d.index.hour == eh) & (d.index.dayofweek == 0)]
        close_m, close_b = d['Close'], d['Close_b']
        jt = e.index.normalize() + pd.Timedelta(days=doff, hours=jh - 1)
        v = jt.isin(close_m.index)
        ee = e[v]
        win_m = close_m.loc[jt[v]].to_numpy() > ee['Open'].to_numpy()
        win_b = close_b.loc[jt[v]].to_numpy() > ee['Open_b'].to_numpy()
        n = len(ee)
        wr_m, wr_b = win_m.mean() * 100, win_b.mean() * 100
        p = stats.binom.sf(int(win_m.sum()) - 1, n, BE / 100)
        yr = ee.index.year.to_numpy()
        jk = min(win_m[yr != y].mean() * 100 - 2.0 - BE for y in np.unique(yr))
        mid_idx = len(ee) // 2
        h1 = win_m[:mid_idx].mean() * 100 - 2.0 - BE
        h2 = win_m[mid_idx:].mean() * 100 - 2.0 - BE
        rows.append(dict(pair=pair, entry=eh, judge=f"{'当日' if doff==0 else '翌'}{jh}時",
                         n=n, wr_bid=round(wr_b, 2), wr_mid=round(wr_m, 2),
                         edge_mid=round(wr_m - 2.0 - BE, 2), p=p, sig=p < ALPHA,
                         h1=round(h1, 2), h2=round(h2, 2), jk_min=round(jk, 2)))

r = pd.DataFrame(rows).sort_values('edge_mid', ascending=False)
r.to_csv(SP / 'monday_variants_mid.csv', index=False, encoding='utf-8-sig')
print(f'月曜バリアント確認試験: {N_TESTS}検定 α={ALPHA:.2e}(ファミリー内補正)')
print(r.to_string(index=False))
print('\n合格(sig & 半期/JK>0):')
ok = r[r['sig'] & (r['h1'] > 0) & (r['h2'] > 0) & (r['jk_min'] > 0)]
print(ok.to_string(index=False) if len(ok) else '(なし)')
