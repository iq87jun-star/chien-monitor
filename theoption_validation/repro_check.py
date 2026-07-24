#!/usr/bin/env python3
"""データ再現性チェック: README記載の親アノマリー数値の再現"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/bb965c91-9b36-5899-9568-61e61c2aee05/scratchpad/hourly')

def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)  # UTC->JST
    return df.set_index('datetime').sort_index()

def check(pair, eh, jh, direction, exp_n, exp_wr):
    df = load(pair)
    close = df['Close']
    e = df[df.index.hour == eh]['Open']
    # 判定 jh時 = jh-1時足の終値 (同日)
    xt = e.index.normalize() + pd.Timedelta(hours=jh - 1)
    v = xt.isin(close.index)
    e = e[v]
    win_high = close.loc[xt[v]].to_numpy() > e.to_numpy()
    w = win_high if direction == 'HIGH' else ~win_high
    n = len(e); wr = w.mean() * 100
    ok = (n == exp_n) and abs(wr - exp_wr) < 0.02
    print(f"{pair} {eh:02d}->{jh:02d} {direction}: n={n} (exp {exp_n}) WR={wr:.2f}% (exp {exp_wr}) {'OK' if ok else 'MISMATCH'}")

check('EURGBP', 7, 11, 'HIGH', 2701, 64.86)
check('EURGBP', 7, 14, 'HIGH', 2701, 63.20)
check('USDCHF', 7, 14, 'HIGH', 2702, 59.51)
check('USDCHF', 7, 11, 'HIGH', 2702, 60.21)
