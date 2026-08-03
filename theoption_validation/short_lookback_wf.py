#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短期検証採用のウォークフォワード実験:
毎月、直近L ヶ月の補正後Edgeランキング上位K セルを選び、翌月そのまま運用(1セル3,000円)。
ユニバース: 11ペア × entry 0-23時 × 判定{1h, 翌6} × (Mon-Fri+ALL) × H/L (ミッド、ヘアカット-2pp)。
比較: 10年検証ポートフォリオ(月曜翌6×5 + AUDJPY8→9h)を同一評価期間・同一総ステークで。"""
import pandas as pd
import numpy as np
from pathlib import Path

SCRATCH = Path('/tmp/claude-0/-home-user-chien-monitor/0001b083-e884-5be9-bded-0678e347fcb1/scratchpad')
BIDD = SCRATCH/'hourly'; ASKD = SCRATCH/'hourly_ask'
START = pd.Timestamp('2016-01-01'); CUTOFF = pd.Timestamp('2026-05-01')
PAIRS = ['EURGBP','USDCHF','GBPJPY','AUDJPY','GBPUSD','NZDJPY','CADJPY','EURJPY','AUDUSD','CHFJPY','EURAUD']
STAKE = 3000; K = 10
BE = {'1h': 100/1.90, 'n6': 100/1.95}
PAY = {'1h': 1.90, 'n6': 1.95}

def load_mid(pair):
    b = pd.read_csv(BIDD/f'{pair}_hourly.csv'); b = b[b['Volume'] > 0]
    a = pd.read_csv(ASKD/f'{pair}_hourly.csv')
    for d in (b, a): d['datetime'] = pd.to_datetime(d['datetime'], format='ISO8601') + pd.Timedelta(hours=9)
    b = b.set_index('datetime').sort_index(); a = a.set_index('datetime').sort_index()
    ix = b.index.intersection(a.index)
    return pd.DataFrame({'Open': (b['Open'].loc[ix]+a['Open'].loc[ix])/2,
                         'Close': (b['Close'].loc[ix]+a['Close'].loc[ix])/2})

# 基本テーブル: (pair, judge, hour) ごとの日次 win_high (index=取引日)
base = {}
for pair in PAIRS:
    df = load_mid(pair); df = df[(df.index >= START) & (df.index < CUTOFF)]
    close = df['Close']
    for eh in range(24):
        bars = df[df.index.hour == eh]
        if len(bars) < 100: continue
        # 1h
        w = bars['Close'].to_numpy() > bars['Open'].to_numpy()
        base[(pair, '1h', eh)] = pd.Series(w.astype(np.int8), index=bars.index.normalize())
        # 翌6
        xt = bars.index.normalize() + pd.Timedelta(days=1, hours=6) - pd.Timedelta(hours=1)
        v = np.asarray(xt.isin(df.index)) & np.asarray((xt + pd.Timedelta(hours=1)) > bars.index)
        if v.sum() < 100: continue
        w6 = close.loc[xt[v]].to_numpy() > bars['Open'].to_numpy()[v]
        base[(pair, 'n6', eh)] = pd.Series(w6.astype(np.int8), index=bars.index[v].normalize())
    print(pair, 'built', flush=True)

months = pd.period_range('2016-01', '2026-04', freq='ME')
SCOPES = list(range(5)) + ['ALL']

def run_wf(lookback_m):
    recs = []
    for i in range(lookback_m, len(months) - 0):
        m = months[i]
        lb_start = months[i-lookback_m].to_timestamp()
        lb_end = m.to_timestamp()
        m_end = (m + 1).to_timestamp()
        # ランキング
        cands = []
        for (pair, judge, eh), s in base.items():
            lb = s[(s.index >= lb_start) & (s.index < lb_end)]
            if len(lb) == 0: continue
            dow = lb.index.dayofweek
            for scope in SCOPES:
                sel = lb if scope == 'ALL' else lb[dow == scope]
                n = len(sel)
                if n < (10 if lookback_m <= 6 else 20): continue
                wr_h = sel.mean()
                for direction, wr in [('H', wr_h), ('L', 1-wr_h)]:
                    edge = wr*100 - 2 - BE[judge]
                    cands.append((edge, pair, judge, eh, scope, direction))
        cands.sort(key=lambda x: -x[0])
        top = cands[:K]
        # 翌月運用
        pnl = 0.0; lb_edges = []; fw_edges = []
        for edge, pair, judge, eh, scope, direction in top:
            s = base[(pair, judge, eh)]
            fw = s[(s.index >= lb_end) & (s.index < m_end)]
            if scope != 'ALL': fw = fw[fw.index.dayofweek == scope]
            if len(fw) == 0: continue
            w = fw.to_numpy().astype(bool)
            if direction == 'L': w = ~w
            po = PAY[judge]
            pnl += (np.where(w, po-1, -1.0) - 0.02*po).sum() * STAKE
            lb_edges.append(edge)
            fw_edges.append(w.mean()*100 - 2 - BE[judge])
        recs.append(dict(month=str(m), pnl=pnl,
                         lb_edge=np.mean(lb_edges) if lb_edges else np.nan,
                         fw_edge=np.mean(fw_edges) if fw_edges else np.nan))
    r = pd.DataFrame(recs)
    eq = r['pnl'].cumsum()
    dd = (eq - eq.cummax()).min()
    print(f'\n== ルックバック{lookback_m}ヶ月・上位{K}セル採用 (毎月入替, 1セル{STAKE}円) ==')
    print(f'評価期間: {r["month"].iloc[0]}〜{r["month"].iloc[-1]} ({len(r)}ヶ月)')
    print(f'月平均P&L={r["pnl"].mean():,.0f}円 累積={r["pnl"].sum():,.0f}円 勝ち月={(r["pnl"]>0).mean()*100:.0f}% 最大DD={dd:,.0f}円')
    print(f'選択時の平均Edge(ルックバック)={r["lb_edge"].mean():+.1f}pp → 翌月の実現Edge={r["fw_edge"].mean():+.1f}pp')
    return r

r6 = run_wf(6)
r12 = run_wf(12)

# 比較: 10年検証メニュー(月曜翌6×5 + AUDJPY8→9h)を同じ評価期間・同等ステークで
sel_menu = [('EURJPY','n6',7,0,'H'),('AUDJPY','n6',7,0,'H'),('NZDJPY','n6',7,0,'H'),
            ('CADJPY','n6',7,0,'H'),('GBPJPY','n6',7,0,'H'),('AUDJPY','1h',8,0,'H')]
for label, start_m in [('6ヶ月版と同期間', months[6]), ('12ヶ月版と同期間', months[12])]:
    t0 = start_m.to_timestamp()
    pnl_m = {}
    for pair, judge, eh, scope, d in sel_menu:
        s = base[(pair, judge, eh)]
        s = s[(s.index >= t0)]
        s = s[s.index.dayofweek == scope]
        po = PAY[judge]
        p = (np.where(s.to_numpy().astype(bool), po-1, -1.0) - 0.02*po) * (STAKE*10/6)  # 総額を揃える(10セル×3000=3万→6本で3万)
        ser = pd.Series(p, index=s.index).groupby(pd.Grouper(freq='ME')).sum()
        for k, v in ser.items(): pnl_m[k] = pnl_m.get(k, 0) + v
    ser = pd.Series(pnl_m).sort_index()
    eq = ser.cumsum(); dd = (eq - eq.cummax()).min()
    print(f'\n== 10年検証メニュー ({label}, 総ステーク同等) ==')
    print(f'月平均P&L={ser.mean():,.0f}円 累積={ser.sum():,.0f}円 勝ち月={(ser>0).mean()*100:.0f}% 最大DD={dd:,.0f}円')
