#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPS実測で確定した商品仕様に基づく2ファミリーの事前登録検証 (2026-10-20)
F1: FE 1H商品 (保有1時間, ペイアウト1.90確定) — エントリー7..23時 → 1時間後判定
F2: FE 22H/23H商品の未検証出口 — エントリー7..23時 → 翌日(エントリー-1h / -2h)判定 (翌7時以降のみ=既検証の翌0-6時は除外)
ゲート: 家族内Bonferroni + Wilson>BE + 前後半Edge>0 + 年抜きJK>0 + 順列検定(曜日型のみ)
補正: -2.0pp。F1はBE=52.63%(1.90)、F2はBE=51.28%(1.95)。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

BASE = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad')
PAIRS = ['EURGBP','USDCHF','GBPJPY','AUDJPY','GBPUSD','NZDJPY','CADJPY','EURJPY','AUDUSD','CHFJPY']
CORR = 2.0
WD = ['Mon','Tue','Wed','Thu','Fri']

def wilson_low(w, n, z=1.96):
    p = w/n; d = 1+z*z/n; c = p+z*z/(2*n)
    m = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (c-m)/d*100

def perm_p(win, mask, obs, ns=200):
    n = len(win); sh = np.unique(np.linspace(1, n-1, ns).astype(int))
    null = np.array([np.roll(win, k)[mask].mean()*100 for k in sh])
    return (1 + (null >= obs).sum())/(1+len(sh))

def run_family(configs, payout, M, fam):
    """configs: list of (entry_h, judgment_h, next_day)"""
    BE = 100/payout
    alpha = 0.05/M
    finals = []
    tested = 0
    for pair in PAIRS:
        df = pd.read_csv(BASE/'hourly'/f'{pair}_hourly.csv')
        df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
        df = df.set_index('datetime').sort_index()
        close = df['Close']
        for eh, jh, nd in configs:
            e = df['Open'][df.index.hour == eh]
            xt = e.index.normalize() + pd.Timedelta(days=1 if nd else 0, hours=jh) - pd.Timedelta(hours=1)
            v = xt.isin(close.index) & ((e.index.normalize() + pd.Timedelta(days=1 if nd else 0, hours=jh)) > e.index)
            e = e[v]
            if len(e) < 1000: continue
            winH = close.loc[xt[v]].to_numpy() > e.to_numpy()
            wd = e.index.dayofweek.to_numpy(); yr = e.index.year.to_numpy()
            for scope in range(6):
                mask = np.ones(len(e), bool) if scope == 5 else (wd == scope)
                n = int(mask.sum())
                if n < 200: continue
                for d, w in [('HIGH', winH), ('LOW', ~winH)]:
                    tested += 1
                    wins = int(w[mask].sum()); wr = wins/n*100
                    p = stats.binom.sf(wins-1, n, BE/100)
                    if p >= alpha or wilson_low(wins, n) <= BE: continue
                    idx = np.where(mask)[0]; mid = idx[len(idx)//2]
                    e1 = w[idx[idx <= mid]].mean()*100 - CORR - BE
                    e2 = w[idx[idx > mid]].mean()*100 - CORR - BE
                    if e1 <= 0 or e2 <= 0: continue
                    jk = min(w[mask & (yr != y)].mean()*100 - CORR - BE for y in np.unique(yr[mask]))
                    if jk <= 0: continue
                    pp = perm_p(w.astype(float), mask, wr) if scope != 5 else None
                    finals.append(dict(family=fam, pair=pair, entry=eh,
                        judgment=('翌' if nd else '当')+f'{jh:02d}時', scope='ALL' if scope==5 else WD[scope],
                        dir=d, n=n, wr=round(wr,2), edge=round(wr-CORR-BE,2), p=f'{p:.1e}',
                        h1=round(e1,2), h2=round(e2,2), jk=round(jk,2),
                        perm=(None if pp is None else round(pp,3)),
                        grade='STRONG' if (pp is None or pp < 0.05) else 'LEAD'))
        print(fam, pair, 'done', flush=True)
    return finals, tested, alpha

# F1: 1時間保有 (当日 eh→eh+1時判定; 23時は翌0時)
f1_cfg = [(eh, (eh+1) % 24, eh == 23) for eh in range(7, 24)]
# F2: 22H/23H → 翌日の(eh-1)/(eh-2)時判定。既検証の翌0-6時は除外(= judgment>=7)
f2_cfg = [(eh, eh-k, True) for eh in range(7, 24) for k in (1, 2) if eh-k >= 7]

M1 = 10*len(f1_cfg)*6*2
M2 = 10*len(f2_cfg)*6*2
r1, t1, a1 = run_family(f1_cfg, 1.90, M1, 'F1-1H')
r2, t2, a2 = run_family(f2_cfg, 1.95, M2, 'F2-22/23H')
print(f"\nF1: 登録M={M1} 実測{t1} α={a1:.2e} 合格{len(r1)}")
print(f"F2: 登録M={M2} 実測{t2} α={a2:.2e} 合格{len(r2)}")
res = pd.DataFrame(r1 + r2)
if len(res):
    res = res.sort_values('edge', ascending=False)
    res.to_csv(BASE/'fe_products_final.csv', index=False, encoding='utf-8-sig')
    print(res.to_string(index=False))
