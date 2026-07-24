#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase2 F2: クロスアセット条件付きエントリー検証 (2026-07-24)
事前登録: prereg_phase2_entry_families.md

コア10戦略 × ドライバー2系列(USDJPY/EURUSD) × 前夜方向2水準 = M=40
前夜 = 前日17:00バーOpen → 当日07:00バーOpen のリターン符号
検定: 条件上下2群の2標本比率検定(uplift)。α=0.05/40=1.25e-03
採用: p<α かつ 条件下n≥300 かつ 前半/後半両方でuplift>0
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/bb965c91-9b36-5899-9568-61e61c2aee05/scratchpad/hourly')
OUT = Path(__file__).parent

def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    return df.set_index('datetime').sort_index()

# 統合ポートフォリオ10戦略 (追補3/4のメニュー固定)
# (name, pair, entry_h, weekdays, judge('h'=同日h時,'n2','n6'), direction, 停止月)
STRATS = [
    ('EURGBP_D_7-11H',  'EURGBP', 7,  [0,1,2,3,4], ('h', 11), 'HIGH', []),
    ('GBPJPY_M_7-14H',  'GBPJPY', 7,  [0],         ('h', 14), 'HIGH', []),
    ('AUDJPY_M_7-n2H',  'AUDJPY', 7,  [0],         ('n', 2),  'HIGH', []),
    ('GBPUSD_M_7-14H',  'GBPUSD', 7,  [0],         ('h', 14), 'HIGH', []),
    ('NZDJPY_M_7-14H',  'NZDJPY', 7,  [0],         ('h', 14), 'HIGH', []),
    ('CADJPY_M_7-14H',  'CADJPY', 7,  [0],         ('h', 14), 'HIGH', []),
    ('EURJPY_M_7-n6H',  'EURJPY', 7,  [0],         ('n', 6),  'HIGH', []),
    ('USDCHF_D_7-14H',  'USDCHF', 7,  [0,1,2,3,4], ('h', 14), 'HIGH', []),
    ('EURGBP_E_23-n6L', 'EURGBP', 23, [0,1,2,4],   ('n', 6),  'LOW',  [2,3,6,12]),
    ('EURAUD_D_10-n6L', 'EURAUD', 10, [0,1,2,3,4], ('n', 6),  'LOW',  []),
]

def build_trades(pair, eh, wds, judge, direction, skip_months):
    df = load(pair)
    close = df['Close']
    e = df[df.index.hour == eh]['Open']
    e = e[e.index.dayofweek.isin(wds)]
    if skip_months:
        e = e[~e.index.month.isin(skip_months)]
    kind, jh = judge
    if kind == 'h':
        xt = e.index.normalize() + pd.Timedelta(hours=jh - 1)
    else:
        xt = e.index.normalize() + pd.Timedelta(days=1, hours=jh) - pd.Timedelta(hours=1)
    v = xt.isin(close.index)
    e = e[v]
    win_high = close.loc[xt[v]].to_numpy() > e.to_numpy()
    win = win_high if direction == 'HIGH' else ~win_high
    return pd.Series(win, index=e.index)

# ドライバー前夜リターン (日付 -> sign)
def driver_sign(pair):
    df = load(pair)
    o = df[df.index.hour.isin([7, 17])]['Open']
    o7 = o[o.index.hour == 7]
    o17 = o[o.index.hour == 17]
    o17d = pd.Series(o17.to_numpy(), index=o17.index.normalize())
    ret = {}
    for t, v in zip(o7.index, o7.to_numpy()):
        prev = t.normalize() - pd.Timedelta(days=1)
        # 前日が存在しない(月曜)は金曜17時を使う
        for back in range(1, 4):
            p = t.normalize() - pd.Timedelta(days=back)
            if p in o17d.index:
                ret[t.normalize()] = np.sign(v - o17d.loc[p])
                break
    return pd.Series(ret)

drivers = {d: driver_sign(d) for d in ['USDJPY', 'EURUSD']}

rows = []
for name, pair, eh, wds, judge, direction, skip in STRATS:
    win = build_trades(pair, eh, wds, judge, direction, skip)
    dates = win.index.normalize()
    mid = win.index[len(win) // 2]
    half2 = win.index > mid
    for dname, dsig in drivers.items():
        sig = dsig.reindex(dates).to_numpy()
        for cond_label, cond in [('up', sig > 0), ('down', sig < 0)]:
            a = win.to_numpy()[cond]
            b = win.to_numpy()[~cond & ~np.isnan(sig)]
            na, nb = len(a), len(b)
            if na == 0 or nb == 0:
                continue
            wa, wb = a.mean(), b.mean()
            pool = (a.sum() + b.sum()) / (na + nb)
            se = np.sqrt(pool * (1 - pool) * (1 / na + 1 / nb))
            z = (wa - wb) / se if se > 0 else 0
            p = stats.norm.sf(abs(z)) * 2
            u1 = a[~half2[cond]].mean() - b[~half2[~cond & ~np.isnan(sig)]].mean() if na else np.nan
            h2c = half2[cond]; h2b = half2[~cond & ~np.isnan(sig)]
            u_h1 = a[~h2c].mean() - b[~h2b].mean() if (~h2c).sum() and (~h2b).sum() else np.nan
            u_h2 = a[h2c].mean() - b[h2b].mean() if h2c.sum() and h2b.sum() else np.nan
            rows.append(dict(strategy=name, driver=dname, cond=cond_label,
                             n_cond=na, wr_cond=round(wa * 100, 2),
                             n_rest=nb, wr_rest=round(wb * 100, 2),
                             uplift=round((wa - wb) * 100, 2), p=p,
                             uplift_h1=round(u_h1 * 100, 2), uplift_h2=round(u_h2 * 100, 2)))

res = pd.DataFrame(rows)
ALPHA = 0.05 / 40
res['pass'] = (res.p < ALPHA) & (res.n_cond >= 300) & (res.uplift_h1 > 0) & (res.uplift_h2 > 0)
res.to_csv(OUT / 'phase2_f2_results.csv', index=False)
print(f"検定数: {len(res)} / α={ALPHA:.2e} / 合格: {res['pass'].sum()}")
print(res.nsmallest(8, 'p')[['strategy', 'driver', 'cond', 'n_cond', 'wr_cond', 'wr_rest', 'uplift', 'p', 'uplift_h1', 'uplift_h2', 'pass']].to_string(index=False))
