#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配分最適化: Edge比例(追補3)を出発点に、相関を考慮したDD制約下の賭金最適化 (2026-07-24)

- 各戦略の1000円単位トレードP&LをIS期間(〜2026-05-23)で構築し日次集計
- 目的: 月平均P&L最大化
- 制約: ヒストリカル最大DD ≤ 予算(20/30/40万円), 1戦略上限20,000円, 1000円刻み
- 解法: グリーディ増分(限界EV/限界DD比) + ペアワイズスワップ改善
- 監査: 週ブロック・ブートストラップ(1000本)でDD分布(p50/p95)を現行配分と比較
- 最後に採用配分のOOS(2026-05-23以降)成績を計測

注意: DDのIS最適化は過学習リスクがあるため、ブートストラップp95と
Edge比例配分との比較を必ず併記し、大差ない場合は現行を維持する裁定とする。
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')
CUTOFF = pd.Timestamp('2026-05-26')  # アンカー一致で確定した検証カットオフ
STEP, CAP = 1000, 20000
WD = dict(Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)

# (名前, ペア, 曜日, entry時, (判定日off,判定時), 方向, ペイアウト, 現行賭金, 停止月)
MENU = [
    ('EURGBP_D_7-11H',   'EURGBP', None,               7, (0, 11), 'H', 1.90, 14000, ()),
    ('GBPJPY_Mon_7-14H', 'GBPJPY', ['Mon'],            7, (0, 14), 'H', 1.95, 14000, ()),
    ('AUDJPY_Mon_7-n2H', 'AUDJPY', ['Mon'],            7, (1, 2),  'H', 1.95, 14000, ()),
    ('GBPUSD_Mon_7-14H', 'GBPUSD', ['Mon'],            7, (0, 14), 'H', 1.95, 13000, ()),
    ('NZDJPY_Mon_7-14H', 'NZDJPY', ['Mon'],            7, (0, 14), 'H', 1.95, 13000, ()),
    ('CADJPY_Mon_7-14H', 'CADJPY', ['Mon'],            7, (0, 14), 'H', 1.95, 12000, ()),
    ('EURJPY_Mon_7-n6H', 'EURJPY', ['Mon'],            7, (1, 6),  'H', 1.95, 11000, ()),
    ('USDCHF_D_7-14H',   'USDCHF', None,               7, (0, 14), 'H', 1.95,  9000, ()),
    ('EURGBP_N_23-n6L',  'EURGBP', ['Mon','Tue','Wed','Fri'], 23, (1, 6), 'L', 1.95, 4000, (2, 3, 6, 12)),
    ('EURAUD_D_10-n6L',  'EURAUD', None,              10, (1, 6),  'L', 1.95,  3000, ()),
]
NAMES = [m[0] for m in MENU]
CURRENT = np.array([m[7] for m in MENU], float)


def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    return df.set_index('datetime').sort_index()


def unit_daily():
    """日次 × 戦略 の1000円単位P&L行列(IS/OOS両方)を返す。"""
    dfs = {}
    cols = {}
    for name, pair, wds, eh, (doff, jh), direc, payout, _, moff in MENU:
        if pair not in dfs:
            dfs[pair] = load(pair)
        df = dfs[pair]
        close = df['Close']
        e = df[df.index.hour == eh]['Open']
        if wds is not None:
            e = e[e.index.dayofweek.isin([WD[w] for w in wds])]
        if moff:
            e = e[~e.index.month.isin(moff)]
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


def max_dd(series):
    cum = np.cumsum(series)
    return float(np.min(cum - np.maximum.accumulate(cum)))


def stats_for(D, stakes, label=''):
    port = D.to_numpy() @ (stakes / 1000.0)
    s = pd.Series(port, index=D.index)
    m = s.resample('ME').sum()
    m = m[m != 0]
    return dict(label=label, total=int(stakes.sum()), mean_m=m.mean(), win_m=(m > 0).mean() * 100,
                dd=max_dd(port), worst_y=s.resample('YE').sum().min())


def bootstrap_dd(D, stakes, reps=1000, seed=7):
    rng = np.random.default_rng(seed)
    port = pd.Series(D.to_numpy() @ (stakes / 1000.0), index=D.index)
    weeks = [g.to_numpy() for _, g in port.groupby(pd.Grouper(freq='W'))]
    weeks = [w for w in weeks if len(w)]
    dds = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, len(weeks), len(weeks))
        dds[i] = max_dd(np.concatenate([weeks[j] for j in idx]))
    return np.percentile(dds, 50), np.percentile(dds, 5)  # DDは負値: 悪化側テール=5パーセンタイル


def greedy(D, budget, cap=CAP):
    n = len(NAMES)
    Dn = D.to_numpy()
    stakes = np.zeros(n)
    mean_days = Dn.mean(axis=0)
    while True:
        best, best_score = None, -np.inf
        cur_dd = max_dd(Dn @ (stakes / 1000.0))
        for i in range(n):
            if stakes[i] + STEP > cap:
                continue
            t = stakes.copy(); t[i] += STEP
            dd = max_dd(Dn @ (t / 1000.0))
            if dd < -budget:
                continue
            marg_ev = mean_days[i] * STEP / 1000.0
            marg_dd = max(1.0, cur_dd - dd)
            score = marg_ev / marg_dd
            if score > best_score:
                best_score, best = score, i
        if best is None:
            break
        stakes[best] += STEP
    # スワップ改善: -1k/+1k の交換で月平均が改善しDD制約内なら採用
    improved = True
    while improved:
        improved = False
        for i in range(n):
            if stakes[i] < STEP:
                continue
            for j in range(n):
                if i == j or stakes[j] + STEP > cap:
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

    print('=== 戦略間相関 (IS月次P&L, 1000円単位) ===')
    Mcorr = IS.resample('ME').sum().corr()
    print(Mcorr.round(2).to_string())
    Mcorr.round(3).to_csv(OUT / 'alloc_corr.csv', encoding='utf-8-sig')

    def report(label, stakes):
        r = stats_for(IS, stakes, label)
        b50, b5 = bootstrap_dd(IS, stakes)
        alloc = ', '.join(f'{n}={int(s):,}' for n, s in zip(NAMES, stakes) if s > 0)
        print(f"\n=== {label} ===\n{alloc}")
        print(f"総賭金{r['total']:,}円 月平均{r['mean_m']:+,.0f}円 勝ち月{r['win_m']:.0f}% "
              f"histDD{r['dd']:+,.0f}円 bootDD p50 {b50:+,.0f} / 悪化側p5 {b5:+,.0f}")
        return b5

    report('現行配分(追補3 Edge比例)', CURRENT)

    results = []
    for budget in [200000, 300000, 400000]:
        st = greedy(IS, budget)
        b5 = report(f'最適化DD{budget//10000}万', st)
        results.append((budget, st, b5))

    # 堅牢版: 30万最適解をブートストラップ悪化側p5が-30万に収まるよう縮尺
    st30 = next(st for b, st, _ in results if b == 300000)
    b5_30 = next(b5 for b, _, b5 in results if b == 300000)
    scale = min(1.0, 300000 / abs(b5_30))
    st_robust = np.floor(st30 * scale / STEP) * STEP
    report('堅牢版(boot p5を30万に縮尺)', st_robust)

    for label, stakes in [('現行', CURRENT), ('最適化30万', st30), ('堅牢版', st_robust)]:
        o = stats_for(OOS, stakes, label)
        print(f"OOS({OOS.index.min():%m/%d}〜) {label}: 合計{(OOS.to_numpy()@(stakes/1000.0)).sum():+,.0f}円 "
              f"histDD{o['dd']:+,.0f}円")

    pd.DataFrame({'strategy': NAMES, 'current': CURRENT.astype(int),
                  **{f'opt{b//10000}': st.astype(int) for b, st, _ in results},
                  'robust': st_robust.astype(int)}
                 ).to_csv(OUT / 'alloc_result.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
