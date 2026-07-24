#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase2 F1: クリプト時間帯アノマリー探索 (2026-07-24)
事前登録: prereg_phase2_entry_families.md

探索空間 M=3,072:
  2銘柄(BTCUSDT/ETHUSDT) × エントリー0-23時JST × 8スコープ(月..日+ALL) × HIGH/LOW × 2判定(翌06:00 / +4h)
段階ゲート: G1 Bonferroni(α=0.05/3072) → G2 Wilson>BE → G4 前後半 → G5 年抜きJK → G3 順列(曜日型のみ)
補正: -2.0pp。ペイアウト: +4h判定1.90(BE52.63) / 翌06:00判定1.95(BE51.28)
データ: Binance公式ダンプ(data.binance.vision) 1h、2017-08〜2026-06
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/bb965c91-9b36-5899-9568-61e61c2aee05/scratchpad/hourly')
OUT = Path(__file__).parent
SYMS = ['BTCUSDT', 'ETHUSDT']
# 事前登録のM=3072は算術ミス(2×24×8×2×2=1536)。列挙空間の実数で補正
M = 1536
ALPHA = 0.05 / M
CORR = 2.0
WD_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

def wilson_low(w, n, z=1.96):
    p = w / n; d = 1 + z * z / n; c = p + z * z / (2 * n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d * 100

def perm_p(win, mask, observed_wr, n_shifts=200):
    n = len(win)
    shifts = np.unique(np.linspace(1, n - 1, n_shifts).astype(int))
    null = np.array([np.roll(win, k)[mask].mean() * 100 for k in shifts])
    return (1 + (null >= observed_wr).sum()) / (1 + len(shifts))

cands, finals = [], []
for sym in SYMS:
    df = pd.read_csv(DATA / f'{sym}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)  # UTC→JST
    df = df.set_index('datetime').sort_index()
    close = df['Close']
    for eh in range(24):
        e_all = df[df.index.hour == eh]['Open']
        for judge, payout in [('next6', 1.95), ('plus4h', 1.90)]:
            BE = 100 / payout
            if judge == 'next6':
                xt = e_all.index.normalize() + pd.Timedelta(days=1, hours=6) - pd.Timedelta(hours=1)
            else:
                xt = e_all.index + pd.Timedelta(hours=3)  # +4h判定バー=+3h足のClose
            v = xt.isin(close.index)
            e = e_all[v]
            win_high = close.loc[xt[v]].to_numpy() > e.to_numpy()
            wd = e.index.dayofweek.to_numpy()
            yr = e.index.year.to_numpy()
            mid = e.index[len(e) // 2]
            half2 = np.asarray(e.index > mid)
            for scope in range(8):  # 0-6=Mon..Sun, 7=ALL
                mask = np.ones(len(e), bool) if scope == 7 else (wd == scope)
                n = int(mask.sum())
                nmin = 1000 if scope == 7 else 200
                if n < nmin:
                    continue
                for direction, w in [('HIGH', win_high), ('LOW', ~win_high)]:
                    wins = int(w[mask].sum())
                    wr = wins / n * 100
                    edge = wr - CORR - BE
                    p = stats.binom.sf(wins - 1, n, BE / 100)
                    row = dict(sym=sym, entry=eh, judge=judge, payout=payout,
                               scope='ALL' if scope == 7 else WD_NAMES[scope],
                               dir=direction, n=n, wr=round(wr, 2), edge=round(edge, 2),
                               p=p)
                    if p < ALPHA:
                        wl = wilson_low(wins, n)
                        h1 = mask & ~half2; h2 = mask & half2
                        e1 = w[h1].mean() * 100 - CORR - BE if h1.sum() else -99
                        e2 = w[h2].mean() * 100 - CORR - BE if h2.sum() else -99
                        jk_min = 99
                        for y in np.unique(yr):
                            m2 = mask & (yr != y)
                            if m2.sum():
                                jk_min = min(jk_min, w[m2].mean() * 100 - CORR - BE)
                        row.update(wilson_low=round(wl, 2), edge_h1=round(e1, 2),
                                   edge_h2=round(e2, 2), jk_min=round(jk_min, 2))
                        g2 = wl > BE
                        g4 = (e1 > 0) and (e2 > 0)
                        g5 = jk_min > 0
                        g3p = None
                        g3 = True
                        if scope != 7:
                            g3p = perm_p(w, mask, wr)
                            g3 = g3p < 0.05
                        row.update(g2=g2, g4=g4, g5=g5, g3_perm_p=g3p, g3=g3)
                        cands.append(row)
                        if g2 and g4 and g5 and g3:
                            finals.append(row)
                    else:
                        cands.append(row)

allc = pd.DataFrame(cands)
allc.to_csv(OUT / 'phase2_f1_all_results.csv', index=False)
fin = pd.DataFrame(finals)
fin.to_csv(OUT / 'phase2_f1_finalists.csv', index=False)
print(f"総パターン(実n充足): {len(allc)} / G1通過: {allc['p'].lt(ALPHA).sum()} / 全ゲート合格: {len(fin)}")
if len(fin):
    print(fin[['sym', 'entry', 'judge', 'scope', 'dir', 'n', 'wr', 'edge', 'p', 'jk_min']].to_string())
