#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新規エントリーファミリー事前登録探索 (2026-07-24)

Family A: 深夜・早朝エントリー(0-5時JST) — 既存グリッド(5-13時/6-23時)の完全未探索領域
  16ペア × entry 0..5時 × 判定{当日11時, 当日14時} × (Mon..Fri+ALL) × H/L = M_A 4608
  ゲート: G1 Bonferroni p<0.05/M_A, G2 Wilson95%下限>BE, G4 前後半Edge>0,
          G5 年抜きJK>0, G3 順列検定(曜日型のみ)
  参考として累積補正(プロジェクト累計 M_cum≈25,000)の合否も併記。

Family B: クロスペア条件付き(採用済み毎日型2本のブースト検証)
  ベース: EURGBP 7→11H / USDCHF 7→14H
  条件: {EURUSD, GBPUSD, USDJPY, 相方ペア} の前夜変化(前日23時Close→当日6時Close)の符号
  2ベース × 4条件ペア × 2符号 = 16検定, 二比率検定 α=0.05/16
  (追補5で自ペア夜間逆行のみ+2.6ppを確認済み。他ペア情報に増分があるかを見る)

補正: スプレッド-1.0pp + 減衰-1.0pp = -2.0pp。
ペイアウト: ホライズン7時間以上=1.95(BE51.28), 未満=1.90(BE52.63)。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
PAIRS = ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY',
         'AUDUSD', 'CHFJPY', 'USDJPY', 'EURUSD', 'NZDUSD', 'USDCAD', 'EURAUD', 'GBPAUD']
CORR = 2.0
WD_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
ENTRIES_A = range(0, 6)
JUDGES_A = [11, 14]
M_A = len(PAIRS) * len(ENTRIES_A) * len(JUDGES_A) * 6 * 2
M_CUM = 25000  # プロジェクト累計の実効探索数(3200+2160+3490+1428*7+13+M_A)概算
CUTOFF = pd.Timestamp('2026-05-26')  # 検証期間はISに揃える(OOSは温存)。アンカー一致で確定したカットオフ


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


def family_a(dfs):
    alpha = 0.05 / M_A
    cands, finals = [], []
    for pair in PAIRS:
        df = dfs[pair][dfs[pair].index < CUTOFF]
        close = df['Close']
        for eh in ENTRIES_A:
            e = df[df.index.hour == eh]['Open']
            for jh in JUDGES_A:
                horizon = jh - eh
                payout = 1.95 if horizon >= 7 else 1.90
                be = 100 / payout
                jt = e.index.normalize() + pd.Timedelta(hours=jh - 1)
                v = jt.isin(close.index)
                ee = e[v]
                win_high = close.loc[jt[v]].to_numpy() > ee.to_numpy()
                wd = ee.index.dayofweek.to_numpy()
                yr = ee.index.year.to_numpy()
                mid = ee.index[len(ee) // 2]
                half2 = np.asarray(ee.index > mid)
                for scope in range(6):
                    mask = np.ones(len(ee), bool) if scope == 5 else (wd == scope)
                    n = int(mask.sum())
                    if n < 200:
                        continue
                    for direction, w in [('HIGH', win_high), ('LOW', ~win_high)]:
                        wins = int(w[mask].sum())
                        wr = wins / n * 100
                        edge = wr - CORR - be
                        p = stats.binom.sf(wins - 1, n, be / 100)
                        row = dict(pair=pair, entry_h=eh, judge_h=jh, payout=payout,
                                   scope='ALL' if scope == 5 else WD_NAMES[scope],
                                   direction=direction, n=n, wr=round(wr, 2),
                                   edge_adj=round(edge, 2), wilson=round(wilson_low(wins, n), 2), p=p)
                        cands.append(row)
                        if p >= alpha or row['wilson'] <= be:
                            continue
                        h1 = w[mask & ~half2]; h2 = w[mask & half2]
                        e1 = h1.mean() * 100 - CORR - be
                        e2 = h2.mean() * 100 - CORR - be
                        if e1 <= 0 or e2 <= 0:
                            continue
                        jk = min(w[mask & (yr != y)].mean() * 100 - CORR - be
                                 for y in np.unique(yr[mask]))
                        if jk <= 0:
                            continue
                        pp = perm_p(w.astype(float), mask, wr) if scope != 5 else None
                        finals.append({**row, 'h1_edge': round(e1, 2), 'h2_edge': round(e2, 2),
                                       'jk_min': round(jk, 2), 'perm_p': pp,
                                       'cum_bonf_pass': p < 0.05 / M_CUM,
                                       'grade': 'STRONG' if (pp is None or pp < 0.05) else 'LEAD'})
        print(pair, 'done', flush=True)
    pd.DataFrame(cands).to_csv(OUT / 'famA_all_candidates.csv', index=False, encoding='utf-8-sig')
    f = pd.DataFrame(finals)
    if len(f):
        f = f.sort_values('edge_adj', ascending=False)
    f.to_csv(OUT / 'famA_final.csv', index=False, encoding='utf-8-sig')
    print(f'\nFamily A: α={alpha:.2e} 探索{len(cands)} 合格{len(f)}')
    if len(f):
        print(f.to_string(index=False))
    return f


def family_b(dfs):
    """前夜(前日23時Close→当日6時Close)の符号で条件分岐したときのWR増分。"""
    bases = [('EURGBP', 7, 11, 'H', 1.90, ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']),
             ('USDCHF', 7, 14, 'H', 1.95, ['EURUSD', 'GBPUSD', 'USDJPY', 'EURGBP'])]
    res = []
    n_tests = sum(len(b[5]) for b in bases) * 2
    alpha = 0.05 / n_tests
    for pair, eh, jh, direc, payout, conds in bases:
        df = dfs[pair][dfs[pair].index < CUTOFF]
        close = df['Close']
        e = df[df.index.hour == eh]['Open']
        jt = e.index.normalize() + pd.Timedelta(hours=jh - 1)
        v = jt.isin(close.index)
        e = e[v]
        win = close.loc[jt[v]].to_numpy() > e.to_numpy()
        if direc == 'L':
            win = ~win
        base_wr = win.mean() * 100
        days = e.index.normalize()
        for cpair in conds:
            cdf = dfs[cpair][dfs[cpair].index < CUTOFF]['Close']
            c6 = cdf[cdf.index.hour == 6]
            c23 = cdf[cdf.index.hour == 23]
            c6d = pd.Series(c6.to_numpy(), index=c6.index.normalize())
            c23d = pd.Series(c23.to_numpy(), index=c23.index.normalize() + pd.Timedelta(days=1))
            ov = (c6d - c23d.reindex(c6d.index)).dropna()  # 当日6時 - 前日23時
            ovm = ov.reindex(days)
            valid = ~np.asarray(ovm.isna())
            for sign, lbl in [(1, 'up'), (-1, 'dn')]:
                m = valid & (np.sign(ovm.to_numpy()) == sign)
                n = int(m.sum())
                if n < 100:
                    continue
                wr = win[m].mean() * 100
                # 二比率検定(条件下 vs 補集合)
                m2 = valid & ~m
                z = (win[m].mean() - win[m2].mean()) / np.sqrt(
                    win[valid].mean() * (1 - win[valid].mean()) * (1 / m.sum() + 1 / m2.sum()))
                p = stats.norm.sf(abs(z)) * 2
                res.append(dict(base=f'{pair}{eh}-{jh}{direc}', cond_pair=cpair, overnight=lbl,
                                n=n, wr=round(wr, 2), base_wr=round(base_wr, 2),
                                delta_pp=round(wr - base_wr, 2), p_2prop=round(p, 4),
                                sig=p < alpha))
    r = pd.DataFrame(res).sort_values('delta_pp', ascending=False)
    r.to_csv(OUT / 'famB_crosspair.csv', index=False, encoding='utf-8-sig')
    print(f'\nFamily B: {n_tests}検定 α={alpha:.4f}')
    print(r.to_string(index=False))
    return r


if __name__ == '__main__':
    dfs = {p: load(p) for p in PAIRS}
    family_a(dfs)
    family_b(dfs)
