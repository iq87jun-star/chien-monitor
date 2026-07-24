#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Family C: 1時間先判定(ペイアウト1.90)の全数探索 (2026-07-24)

ザオプションでは任意の時間帯で約1時間先の判定時刻が1.90倍で提供される。
エントリー=H:00バーのOpen、判定=H+1:00(=H:00バーのClose)として
16ペア × 24エントリー時 × (Mon..Fri+ALL) × HIGH/LOW = M 4608 を事前登録。

ゲート(既存プロトコル準拠):
  G1 Bonferroni: binom p < 0.05/4608
  G2 Wilson95%下限 > BE(52.63%)
  G4 前半/後半サブサンプル: 補正後Edge > 0
  G5 年抜きJackknife: 最低Edge > 0
  G3 順列検定200本(曜日型のみ)
補正: スプレッド-1.0pp + 減衰-1.0pp = -2.0pp → 実質必要勝率 54.63%
IS: 〜2026-05-26(アンカー確定カットオフ)。合格戦略はOOS(5/26〜7/23)も併記。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
PAIRS = ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY',
         'AUDUSD', 'CHFJPY', 'USDJPY', 'EURUSD', 'NZDUSD', 'USDCAD', 'EURAUD', 'GBPAUD']
PAYOUT = 1.90
BE = 100 / PAYOUT
CORR = 2.0
M = len(PAIRS) * 24 * 6 * 2
ALPHA = 0.05 / M
WD_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
CUTOFF = pd.Timestamp('2026-05-26')


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


def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    return df.set_index('datetime').sort_index()


cands, finals = [], []
for pair in PAIRS:
    full = load(pair)
    df = full[full.index < CUTOFF]
    oos = full[full.index >= CUTOFF]
    for eh in range(24):
        bars = df[df.index.hour == eh]
        win_high_all = (bars['Close'] > bars['Open']).to_numpy()
        wd = bars.index.dayofweek.to_numpy()
        yr = bars.index.year.to_numpy()
        mid = bars.index[len(bars) // 2]
        half2 = np.asarray(bars.index > mid)
        obars = oos[oos.index.hour == eh]
        owin_high = (obars['Close'] > obars['Open']).to_numpy()
        owd = obars.index.dayofweek.to_numpy()
        for scope in range(6):
            mask = np.ones(len(bars), bool) if scope == 5 else (wd == scope)
            n = int(mask.sum())
            if n < 200:
                continue
            for direction, w in [('HIGH', win_high_all), ('LOW', ~win_high_all)]:
                wins = int(w[mask].sum())
                wr = wins / n * 100
                edge = wr - CORR - BE
                p = stats.binom.sf(wins - 1, n, BE / 100)
                row = dict(pair=pair, entry_h=eh, scope='ALL' if scope == 5 else WD_NAMES[scope],
                           direction=direction, n=n, wr=round(wr, 2), edge_adj=round(edge, 2),
                           wilson=round(wilson_low(wins, n), 2), p=p)
                cands.append(row)
                if p >= ALPHA or row['wilson'] <= BE:
                    continue
                h1 = w[mask & ~half2]; h2 = w[mask & half2]
                e1 = h1.mean() * 100 - CORR - BE
                e2 = h2.mean() * 100 - CORR - BE
                if e1 <= 0 or e2 <= 0:
                    continue
                jk = min(w[mask & (yr != y)].mean() * 100 - CORR - BE
                         for y in np.unique(yr[mask]))
                if jk <= 0:
                    continue
                pp = perm_p(w.astype(float), mask, wr) if scope != 5 else None
                om = np.ones(len(obars), bool) if scope == 5 else (owd == scope)
                ow = owin_high if direction == 'HIGH' else ~owin_high
                o_n = int(om.sum())
                o_wr = round(ow[om].mean() * 100, 2) if o_n else None
                finals.append({**row, 'h1_edge': round(e1, 2), 'h2_edge': round(e2, 2),
                               'jk_min': round(jk, 2), 'perm_p': pp,
                               'oos_n': o_n, 'oos_wr': o_wr,
                               'grade': 'STRONG' if (pp is None or pp < 0.05) else 'LEAD'})
    print(pair, 'done', flush=True)

pd.DataFrame(cands).to_csv(OUT / 'famC_1h_all_candidates.csv', index=False, encoding='utf-8-sig')
f = pd.DataFrame(finals)
if len(f):
    f = f.sort_values('edge_adj', ascending=False)
f.to_csv(OUT / 'famC_1h_final.csv', index=False, encoding='utf-8-sig')
print(f'\nFamily C(1時間判定): M={M} α={ALPHA:.2e} 探索{len(cands)} 合格{len(f)}')
if len(f):
    print(f.to_string(index=False))
else:
    # 参考: 補正前Edgeが正で有意に最も近かった上位を表示
    c = pd.DataFrame(cands).sort_values('p').head(15)
    print('\n(参考)p値上位15 — いずれも不合格:')
    print(c.to_string(index=False))
