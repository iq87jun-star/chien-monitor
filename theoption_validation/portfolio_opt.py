#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""統合ポートフォリオ(追補3)の再構築と配分改善。
1) 10戦略のトレード系列を再構築し、現行Edge比例配分の月期待/DD/勝ち月率を再現
2) 戦略間相関を測定
3) DD制約(30万円)下の配分最適化: 履歴DD制約 + 月次ブロックブートストラップP95 DD制約の2本立て
4) 現行配分との比較 + 2026年6-7月アウトオブサンプル成績
"""
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
DATA = SCRATCH/'hourly'
OUT = SCRATCH
rng = np.random.default_rng(20260724)

START = pd.Timestamp('2016-01-01')
CUTOFF = pd.Timestamp('2026-05-24')   # 探索に使われた期間の終端(再現用)
OOS_END = pd.Timestamp('2026-07-25')  # 6-7月OOS
DD_BUDGET = 300_000

# (name, pair, scope, entry_h, judgment, direction, payout, current_stake, excl_months)
MENU = [
    ('EURGBP毎日7→11H',  'EURGBP','ALL',7,('same',11),'HIGH',1.90,14000,()),
    ('GBPJPY月7→14H',    'GBPJPY','Mon',7,('same',14),'HIGH',1.95,14000,()),
    ('AUDJPY月7→翌2H',   'AUDJPY','Mon',7,('next',2),'HIGH',1.95,14000,()),
    ('GBPUSD月7→14H',    'GBPUSD','Mon',7,('same',14),'HIGH',1.95,13000,()),
    ('NZDJPY月7→14H',    'NZDJPY','Mon',7,('same',14),'HIGH',1.95,13000,()),
    ('CADJPY月7→14H',    'CADJPY','Mon',7,('same',14),'HIGH',1.95,12000,()),
    ('EURJPY月7→翌6H',   'EURJPY','Mon',7,('next',6),'HIGH',1.95,11000,()),
    ('USDCHF毎日7→14H',  'USDCHF','ALL',7,('same',14),'HIGH',1.95,9000,()),
    ('EURGBP23→翌6L',    'EURGBP','ALL',23,('next',6),'LOW',1.95,4000,(2,3,6,12)),
    ('EURAUD10→翌6L',    'EURAUD','ALL',10,('next',6),'LOW',1.95,3000,()),
]

frames = {}
def load(pair):
    if pair not in frames:
        df = pd.read_csv(DATA/f'{pair}_hourly.csv')
        df = df[df['Volume'] > 0]
        df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
        frames[pair] = df.set_index('datetime').sort_index()
    return frames[pair]

def build(name, pair, scope, eh, judgment, direction, payout, stake, excl, end, haircut=True):
    df = load(pair)
    e = df[(df.index.hour == eh) & (df.index >= START) & (df.index < end)]['Open']
    kind, jh = judgment
    xt = e.index.normalize() + pd.Timedelta(days=(1 if kind=='next' else 0), hours=jh) - pd.Timedelta(hours=1)
    v = xt.isin(df.index) & ((xt + pd.Timedelta(hours=1)) > e.index)
    e = e[v]
    win = df['Close'].loc[xt[v]].to_numpy() > e.to_numpy()
    if direction == 'LOW': win = ~win
    m = np.ones(len(e), bool)
    if scope != 'ALL': m &= (e.index.dayofweek == 0)
    if excl: m &= ~e.index.month.isin(excl)
    idx = e.index[m]; w = win[m]
    pnl_unit = np.where(w, payout-1.0, -1.0)   # 掛け金1円あたり
    if haircut:
        pnl_unit = pnl_unit - 0.02*payout      # -2.0pp勝率補正の期待コスト(前セッション流儀)
    return pd.Series(pnl_unit, index=idx.normalize(), name=name)

series, series_oos = [], []
for row in MENU:
    series.append(build(*row[:8], row[8], CUTOFF, haircut=True))
    series_oos.append(build(*row[:8], row[8], OOS_END, haircut=False))

# 日次テーブル(戦略×日, 1円あたり)
daily = pd.concat([s.groupby(level=0).sum() for s in series], axis=1).fillna(0.0)
daily.columns = [r[0] for r in MENU]
monthly = daily.groupby([daily.index.year, daily.index.month]).sum()
stakes_cur = np.array([r[7] for r in MENU], float)

def evaluate(stakes, label):
    d = daily @ stakes
    mth = monthly @ stakes
    eq = d.cumsum()
    dd = (eq - eq.cummax()).min()
    yearly = d.groupby(d.index.year).sum()
    res = dict(label=label, monthly_mean=mth.mean(), annual=mth.mean()*12,
               max_dd=dd, win_month=(mth>0).mean()*100,
               worst_year=yearly.min(), losing_years=int((yearly<0).sum()))
    return res, mth

def boot_dd(stakes, n=2000, rng=rng):
    """月次ブロックブートストラップの最大DD分布(10年パス)"""
    mvals = (monthly @ stakes).to_numpy()
    k = len(mvals)
    dds = np.empty(n)
    for i in range(n):
        path = np.cumsum(mvals[rng.integers(0, k, k)])
        dds[i] = (path - np.maximum.accumulate(np.maximum(path, 0))).min()
    return np.percentile(dds, [50, 90, 95])

print('== 戦略別(掛け金1000円あたり, 〜2026-05-23) ==')
for s in series:
    wr = (s > 0).mean()*100
    print(f"{s.name:<18} n={len(s):5d} WR={wr:6.2f}% 月平均={s.sum()/((CUTOFF-START).days/30.44)*1000:8.0f}円/1000円")

print('\n== 戦略間相関(月次P&L, 1円あたり) ==')
cm = monthly.corr().round(2)
print(cm.to_string())
cm.to_csv(OUT/'portfolio_corr.csv', encoding='utf-8-sig')

res_cur, mth_cur = evaluate(stakes_cur, '現行Edge比例')
print('\n== 現行配分の再現 ==')
print({k: round(v,0) if isinstance(v,float) else v for k,v in res_cur.items()})
print('bootstrap DD [P50,P90,P95]:', boot_dd(stakes_cur).round(0))

# ---- 最適化: 履歴DD<=30万 かつ ブートストラップP95 DD<=30万 で月期待最大化 ----
# 座標上昇 + マルチスタート(離散1000円刻み, 上限は現行合計の1.6倍/戦略上限20k)
def hist_dd(stakes):
    d = daily @ stakes
    eq = d.cumsum()
    return (eq - eq.cummax()).min()

def objective(stakes):
    return (monthly @ stakes).mean()

STEP, SMAX = 1000, 20000
def feasible(stakes):
    if hist_dd(stakes) < -DD_BUDGET: return False
    return boot_dd(stakes, n=600, rng=np.random.default_rng(7))[2] >= -DD_BUDGET

best = None
for trial in range(6):
    r2 = np.random.default_rng(100+trial)
    x = stakes_cur.copy() if trial == 0 else np.round(r2.uniform(0, 12000, len(MENU))/STEP)*STEP
    while not feasible(x):
        x = np.maximum(0, x - STEP)  # scale down until feasible
        if x.sum() == 0: break
    improved = True
    while improved:
        improved = False
        for i in np.argsort(-monthly.mean().to_numpy()):  # richest edge first
            up = x.copy(); up[i] = min(SMAX, x[i]+STEP)
            if up[i] != x[i] and feasible(up):
                x = up; improved = True
    val = objective(x)
    if best is None or val > best[0]:
        best = (val, x.copy())
    print(f'trial {trial}: monthly={val:,.0f} stakes={x.astype(int).tolist()}')

x_opt = best[1]
res_opt, mth_opt = evaluate(x_opt, '最適化(DD制約30万)')
print('\n== 最適化配分 ==')
for r, k in zip(MENU, x_opt): print(f'{r[0]:<18} {int(k):6d}円 (現行 {r[7]})')
print({k: round(v,0) if isinstance(v,float) else v for k,v in res_opt.items()})
print('bootstrap DD [P50,P90,P95]:', boot_dd(x_opt).round(0))

# ---- OOS 2026-06-01..07-24 ----
print('\n== アウトオブサンプル (2026-05-24以降) ==')
daily_oos = pd.concat([s.groupby(level=0).sum() for s in series_oos], axis=1).fillna(0.0)
daily_oos.columns = [r[0] for r in MENU]
oos = daily_oos[daily_oos.index >= CUTOFF]
for name in oos.columns:
    s = oos[name][oos[name] != 0]
    if len(s) == 0: continue
    wr = (s > 0).mean()*100
    print(f'{name:<18} n={len(s):3d} WR={wr:5.1f}% P&L/1000円={s.sum()*1000:8.0f}円')
print(f'現行配分OOS合計: {(oos @ stakes_cur).sum():,.0f}円  最適化配分OOS合計: {(oos @ x_opt).sum():,.0f}円')

pd.DataFrame({'strategy':[r[0] for r in MENU], 'current':stakes_cur.astype(int),
              'optimized':x_opt.astype(int)}).to_csv(OUT/'portfolio_alloc.csv', index=False, encoding='utf-8-sig')
