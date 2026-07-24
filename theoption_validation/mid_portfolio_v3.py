#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3: 判定提供制約(+1h/翌6:00のみ)下のポートフォリオ (2026-07-24)

mid監査で生き残った戦略のみでメニューを再編:
- 月曜7時ファミリー6本(GBPJPY/GBPUSD/NZDJPY/CADJPY 14時判定, AUDJPY翌2時, EURJPY翌6時)
- 月曜7時の1時間判定2本(EURJPY 7→8, USDJPY 7→8, 1.90倍) ← famC mid生存
- EURGBP夜間LOW(23→翌6, 月火水金, 2/3/6/12月停止)
除外: EURGBP毎日7-11H・USDCHF毎日7-14H(ロールオーバー気配アーティファクト)、
      EURAUD10時LOW(mid補正後Edge≈0)

P&L: mid判定の勝敗、勝ち+stake*(P-1)/負け-stake、全トレード-0.02*P*stakeの補正課金。
配分: グリーディ+スワップ(histDD30万制約・上限20k)、週ブロックbootstrap p5併記、OOS計測。
"""
import pandas as pd
import numpy as np
from pathlib import Path

SP = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')
STEP, CAP = 1000, 20000
WD = dict(Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)

MENU = [  # v3: 判定は+1h(7→8時)と翌6:00のみ(提供制約)
    ('EURJPY_Mon_7-8H',   'EURJPY', ['Mon'], 7, (0, 8),  'H', 1.90, ()),
    ('USDJPY_Mon_7-8H',   'USDJPY', ['Mon'], 7, (0, 8),  'H', 1.90, ()),
    ('EURJPY_Mon_7-n6H',  'EURJPY', ['Mon'], 7, (1, 6),  'H', 1.95, ()),
    ('AUDJPY_Mon_7-n6H',  'AUDJPY', ['Mon'], 7, (1, 6),  'H', 1.95, ()),
    ('NZDJPY_Mon_7-n6H',  'NZDJPY', ['Mon'], 7, (1, 6),  'H', 1.95, ()),
    ('EURGBP_N_23-n6L',   'EURGBP', ['Mon','Tue','Wed','Fri'], 23, (1, 6), 'L', 1.95, (2, 3, 6, 12)),
]
NAMES = [m[0] for m in MENU]


def load_mid(pair):
    b = pd.read_csv(SP / 'hourly' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    a = pd.read_csv(SP / 'hourly_ask' / f'{pair}_hourly.csv', parse_dates=['datetime'])
    m = b.merge(a, on='datetime', suffixes=('_b', '_a'))
    for c in ['Open', 'Close']:
        m[c] = (m[f'{c}_b'] + m[f'{c}_a']) / 2
    m['datetime'] = m['datetime'] + pd.Timedelta(hours=9)
    return m.set_index('datetime').sort_index()


def unit_daily():
    dfs, cols = {}, {}
    for name, pair, wds, eh, (doff, jh), direc, payout, moff in MENU:
        if pair not in dfs:
            dfs[pair] = load_mid(pair)
        df = dfs[pair]
        e = df[df.index.hour == eh]['Open']
        if wds is not None:
            e = e[e.index.dayofweek.isin([WD[w] for w in wds])]
        if moff:
            e = e[~e.index.month.isin(moff)]
        close = df['Close']
        jt = e.index.normalize() + pd.Timedelta(days=doff, hours=jh - 1)
        v = jt.isin(close.index)
        e = e[v]
        jc = close.loc[jt[v]].to_numpy()
        win = (jc > e.to_numpy()) if direc == 'H' else (jc < e.to_numpy())
        pnl = np.where(win, 1000 * (payout - 1), -1000) - 0.02 * payout * 1000
        cols[name] = pd.Series(pnl, index=e.index.normalize())
    days = sorted(set().union(*[set(s.index) for s in cols.values()]))
    D = pd.DataFrame(0.0, index=pd.DatetimeIndex(days), columns=NAMES)
    for name, s in cols.items():
        D[name] = s.groupby(level=0).sum().reindex(D.index).fillna(0.0)
    return D


def max_dd(x):
    c = np.cumsum(x)
    return float(np.min(c - np.maximum.accumulate(c)))


def stats_for(D, stakes):
    port = D.to_numpy() @ (stakes / 1000.0)
    s = pd.Series(port, index=D.index)
    m = s.resample('ME').sum()
    m = m[m != 0]
    return m.mean(), (m > 0).mean() * 100, max_dd(port)


def bootstrap_p5(D, stakes, reps=1000, seed=7):
    rng = np.random.default_rng(seed)
    port = pd.Series(D.to_numpy() @ (stakes / 1000.0), index=D.index)
    weeks = [g.to_numpy() for _, g in port.groupby(pd.Grouper(freq='W')) if len(g)]
    dds = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, len(weeks), len(weeks))
        dds[i] = max_dd(np.concatenate([weeks[j] for j in idx]))
    return np.percentile(dds, 5)


def greedy(D, budget):
    Dn = D.to_numpy()
    n = len(NAMES)
    stakes = np.zeros(n)
    mean_days = Dn.mean(axis=0)
    while True:
        best, best_score = None, -np.inf
        cur_dd = max_dd(Dn @ (stakes / 1000.0))
        for i in range(n):
            if stakes[i] + STEP > CAP:
                continue
            t = stakes.copy(); t[i] += STEP
            dd = max_dd(Dn @ (t / 1000.0))
            if dd < -budget:
                continue
            score = (mean_days[i] * STEP / 1000.0) / max(1.0, cur_dd - dd)
            if score > best_score:
                best_score, best = score, i
        if best is None:
            break
        stakes[best] += STEP
    improved = True
    while improved:
        improved = False
        for i in range(n):
            if stakes[i] < STEP:
                continue
            for j in range(n):
                if i == j or stakes[j] + STEP > CAP:
                    continue
                t = stakes.copy(); t[i] -= STEP; t[j] += STEP
                if (Dn @ (t / 1000.0)).mean() <= (Dn @ (stakes / 1000.0)).mean():
                    continue
                if max_dd(Dn @ (t / 1000.0)) < -budget:
                    continue
                stakes = t; improved = True
    return stakes


def main():
    D = unit_daily()
    IS, OOS = D[D.index < CUTOFF], D[D.index >= CUTOFF]

    print('=== 戦略別 単位(1000円)成績 (IS, mid判定) ===')
    for name in NAMES:
        s = IS[name][IS[name] != 0]
        wr = (s > 0).mean() * 100
        print(f'  {name}: n={len(s)} WR≈{wr:.1f}% 平均{s.mean():+.0f}円/トレード 年計{s.sum()/10.4:+,.0f}円')

    for budget in [300000]:
        st = greedy(IS, budget)
        mean_m, win_m, dd = stats_for(IS, st)
        p5 = bootstrap_p5(IS, st)
        alloc = ', '.join(f'{n}={int(s):,}' for n, s in zip(NAMES, st) if s > 0)
        print(f'\n=== v3最適化 (histDD{budget//10000}万制約) ===\n{alloc}')
        print(f'総賭金{int(st.sum()):,}円 月平均{mean_m:+,.0f}円 勝ち月{win_m:.0f}% histDD{dd:+,.0f}円 boot p5 {p5:+,.0f}円')
        om, ow, odd = stats_for(OOS, st)
        print(f'OOS(5/26-7/23): 合計{(OOS.to_numpy()@(st/1000.0)).sum():+,.0f}円 histDD{odd:+,.0f}円')
        # 堅牢版スケール
        scale = min(1.0, budget / abs(p5))
        st2 = np.floor(st * scale / STEP) * STEP
        m2, w2, dd2 = stats_for(IS, st2)
        p52 = bootstrap_p5(IS, st2)
        print(f'堅牢版(×{scale:.2f}): 総賭金{int(st2.sum()):,}円 月平均{m2:+,.0f}円 boot p5 {p52:+,.0f}円')
        pd.DataFrame({'strategy': NAMES, 'v3_opt30': st.astype(int), 'v3_robust': st2.astype(int)}
                     ).to_csv(SP / 'alloc_v3.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
