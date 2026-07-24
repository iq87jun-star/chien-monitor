#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Family D: BTC/ETH 時間帯アノマリー全数探索 (2026-07-24)

前回来の「残る拡張はBTC/ETHのデータ調達のみ」を実施。
データ: Bitstamp実約定OHLC 1時間足(BTC 2016-, ETH 2017-)。単一価格のため
Dukascopy BIDのようなロールオーバー気配アーティファクトは原理的に無い。

探索空間(事前登録): 2銘柄 × entry 0-23時JST × (Mon..Sun + ALL) × H/L × 判定4種
  判定: +1時間(1.90) / 当日11時 / 当日14時 / 翌日6時 (ホライズン≥7h→1.95, 未満→1.90)
  M = 3072, α = 0.05/M
ゲート: G1 Bonferroni / G2 Wilson>BE / G4 前後半Edge>0 / G5 年抜きJK>0 / G3 順列(曜日型)
補正: -2.0pp(FXと同基準。暗号資産のバイナリはスプレッド実害がより大きい可能性に注意)
IS: 〜2026-05-26。合格はOOS(5/26-7/24)併記。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

SP = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')
ASSETS = ['BTCUSD', 'ETHUSD']
M = 2 * 24 * 8 * 2 * 4
ALPHA = 0.05 / M
DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
JUDGES = [('+1h', None), ('当日11', (0, 11)), ('当日14', (0, 14)), ('翌6', (1, 6))]


def wilson_low(w, n, z=1.96):
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d * 100


def perm_p(win, mask, observed_wr, n_shifts=200):
    n = len(win)
    shifts = np.unique(np.linspace(1, n - 1, n_shifts).astype(int))
    null = np.array([np.roll(win, k)[mask].mean() * 100 for k in shifts])
    return (1 + (null >= observed_wr).sum()) / (1 + len(shifts))


cands, finals = [], []
for asset in ASSETS:
    df = pd.read_csv(SP / 'hourly' / f'{asset}_hourly.csv', parse_dates=['datetime'])
    df['datetime'] = df['datetime'] + pd.Timedelta(hours=9)
    df = df.set_index('datetime').sort_index()
    d = df[df.index < CUTOFF]
    o = df[df.index >= CUTOFF]
    close, oclose = d['Close'], o['Close']
    for eh in range(24):
        e = d[d.index.hour == eh]['Open']
        oe = o[o.index.hour == eh]['Open']
        for jname, judge in JUDGES:
            if judge is None:
                jt = e.index + pd.Timedelta(hours=0)  # 判定=同バーClose
                horizon = 1
                win_high_full = (d[d.index.hour == eh]['Close'].to_numpy() > e.to_numpy())
                ee = e
                owin_high = (o[o.index.hour == eh]['Close'].to_numpy() > oe.to_numpy())
                oee = oe
            else:
                doff, jh = judge
                horizon = (doff * 24 + jh) - eh
                if horizon <= 1:
                    continue
                jt = e.index.normalize() + pd.Timedelta(days=doff, hours=jh - 1)
                v = jt.isin(close.index)
                ee = e[v]
                win_high_full = close.loc[jt[v]].to_numpy() > ee.to_numpy()
                ojt = oe.index.normalize() + pd.Timedelta(days=doff, hours=jh - 1)
                ov = ojt.isin(oclose.index)
                oee = oe[ov]
                owin_high = oclose.loc[ojt[ov]].to_numpy() > oee.to_numpy()
            payout = 1.95 if horizon >= 7 else 1.90
            be = 100 / payout
            wd = ee.index.dayofweek.to_numpy()
            yr = ee.index.year.to_numpy()
            mid = ee.index[len(ee) // 2]
            half2 = np.asarray(ee.index > mid)
            owd = oee.index.dayofweek.to_numpy()
            for scope in range(8):  # 0-6=Mon..Sun, 7=ALL
                mask = np.ones(len(ee), bool) if scope == 7 else (wd == scope)
                n = int(mask.sum())
                if n < 200:
                    continue
                for direction, w in [('HIGH', win_high_full), ('LOW', ~win_high_full)]:
                    wins = int(w[mask].sum())
                    wr = wins / n * 100
                    edge = wr - 2.0 - be
                    p = stats.binom.sf(wins - 1, n, be / 100)
                    row = dict(asset=asset, entry_h=eh, judge=jname, payout=payout,
                               scope='ALL' if scope == 7 else DAY_NAMES[scope],
                               direction=direction, n=n, wr=round(wr, 2),
                               edge_adj=round(edge, 2), wilson=round(wilson_low(wins, n), 2), p=p)
                    cands.append(row)
                    if p >= ALPHA or row['wilson'] <= be:
                        continue
                    h1 = w[mask & ~half2]; h2 = w[mask & half2]
                    e1 = h1.mean() * 100 - 2.0 - be
                    e2 = h2.mean() * 100 - 2.0 - be
                    if e1 <= 0 or e2 <= 0:
                        continue
                    jk = min(w[mask & (yr != y)].mean() * 100 - 2.0 - be for y in np.unique(yr[mask]))
                    if jk <= 0:
                        continue
                    pp = perm_p(w.astype(float), mask, wr) if scope != 7 else None
                    om = np.ones(len(oee), bool) if scope == 7 else (owd == scope)
                    ow = owin_high if direction == 'HIGH' else ~owin_high
                    finals.append({**row, 'h1_edge': round(e1, 2), 'h2_edge': round(e2, 2),
                                   'jk_min': round(jk, 2), 'perm_p': pp,
                                   'oos_n': int(om.sum()),
                                   'oos_wr': round(ow[om].mean() * 100, 1) if om.sum() else None,
                                   'grade': 'STRONG' if (pp is None or pp < 0.05) else 'LEAD'})
    print(asset, 'done', flush=True)

pd.DataFrame(cands).to_csv(SP / 'famD_crypto_all.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals)
if len(f):
    f = f.sort_values('edge_adj', ascending=False)
f.to_csv(SP / 'famD_crypto_final.csv', index=False, encoding='utf-8-sig')
print(f'\nFamily D(BTC/ETH): M={M} α={ALPHA:.2e} 探索{len(cands)} 合格{len(f)}')
if len(f):
    print(f.to_string(index=False))
else:
    c = pd.DataFrame(cands).sort_values('p').head(10)
    print('\n(参考)p値上位10 — いずれも不合格:')
    print(c.to_string(index=False))
