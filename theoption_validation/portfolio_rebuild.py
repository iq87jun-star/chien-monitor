#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合ポートフォリオ(追補3)の再構築・アンカー再現検証・フォワード計測 (2026-07-24)

1. Dukascopyから再取得したデータで既存アンカー(n/WR)を再現し、データ同一性を確認
2. 追補3の10戦略メニューをトレードレベルで再構築し、月次系列・DDを再現
3. 検証カットオフ(2026-05-23)以降の約2ヶ月を真のフォワード(OOS)として計測

P&L規約: 勝ち +stake*(P-1)、負け -stake、全トレードに補正 -0.02*P*stake
(スプレッド+減衰-2ppをEV等価で毎トレード課金 = 追補3のEdge比例期待値と整合)
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad/hourly')
OUT = Path('/tmp/claude-0/-home-user-chien-monitor/4f8a9c39-18e4-5e5b-9f5d-d5832503133b/scratchpad')

WD = dict(Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)

# 追補3メニュー: (名前, ペア, 曜日リストorNone=毎日, entry時, 判定(日オフセット,時), 方向, ペイアウト, 賭金, 停止月)
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

# 再現検証アンカー (g3_g5_results / next6_final / 追補2, データ末尾=検証当時)
ANCHORS = [
    ('EURGBP', None,    7, (0, 11), 'H', 2701, 64.86),
    ('USDCHF', None,    7, (0, 14), 'H', 2702, 59.51),
    ('GBPJPY', ['Mon'], 7, (0, 14), 'H',  537, 62.94),
    ('AUDJPY', ['Mon'], 7, (1, 2),  'H',  537, 62.76),
    ('GBPUSD', ['Mon'], 7, (0, 14), 'H',  538, 62.27),
    ('NZDJPY', ['Mon'], 7, (0, 14), 'H',  537, 62.20),
    ('CADJPY', ['Mon'], 7, (0, 14), 'H',  538, 61.71),
    ('EURJPY', ['Mon'], 7, (1, 6),  'H',  537, 60.71),
    ('EURGBP', None,   23, (1, 6),  'L', 2695, 55.77),
]


def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)  # UTC -> JST
    return df.set_index('datetime').sort_index()


def trades(df, weekdays, eh, judge, direction, months_off=()):
    """エントリーバーOpen vs 判定バー((判定時-1)時バーClose)。勝敗のSeries(index=エントリー時刻)を返す。"""
    d_off, jh = judge
    e = df[df.index.hour == eh]['Open']
    if weekdays is not None:
        e = e[e.index.dayofweek.isin([WD[w] for w in weekdays])]
    if months_off:
        e = e[~e.index.month.isin(months_off)]
    jt = e.index.normalize() + pd.Timedelta(days=d_off, hours=jh - 1)
    close = df['Close']
    v = jt.isin(close.index)
    e = e[v]
    jc = close.loc[jt[v]].to_numpy()
    win = (jc > e.to_numpy()) if direction == 'H' else (jc < e.to_numpy())
    return pd.Series(win, index=e.index)


def main():
    dfs = {p: load(p) for p in
           ['EURGBP', 'USDCHF', 'GBPJPY', 'AUDJPY', 'GBPUSD', 'NZDJPY', 'CADJPY', 'EURJPY', 'EURAUD']}

    # ---- 1. アンカー再現: カットオフをn一致で自己決定 ----
    print('=== アンカー再現検証 ===')
    best_cut, best_hits = None, -1
    for day in pd.date_range('2026-05-17', '2026-06-01'):
        hits = 0
        for pair, wds, eh, judge, direc, ref_n, ref_wr in ANCHORS:
            w = trades(dfs[pair], wds, eh, judge, direc)
            w = w[w.index < day]
            if len(w) == ref_n and abs(w.mean() * 100 - ref_wr) < 0.05:
                hits += 1
        if hits > best_hits:
            best_hits, best_cut = hits, day
    print(f'最良カットオフ {best_cut.date()}: {best_hits}/{len(ANCHORS)} アンカー一致')
    for pair, wds, eh, judge, direc, ref_n, ref_wr in ANCHORS:
        w = trades(dfs[pair], wds, eh, judge, direc)
        w = w[w.index < best_cut]
        ok = '一致' if (len(w) == ref_n and abs(w.mean() * 100 - ref_wr) < 0.05) else '不一致'
        print(f'  {pair} e{eh}h j{judge} {direc}: n={len(w)} (ref {ref_n})  WR={w.mean()*100:.2f} (ref {ref_wr})  {ok}')

    # ---- 2. ポートフォリオ再構築 (全期間 + IS/OOS分割) ----
    rows = []
    for name, pair, wds, eh, judge, direc, payout, stake, moff in MENU:
        w = trades(dfs[pair], wds, eh, judge, direc, moff)
        pnl = np.where(w.to_numpy(), stake * (payout - 1), -stake) - 0.02 * payout * stake
        rows.append(pd.DataFrame({'strategy': name, 'win': w.to_numpy(), 'pnl': pnl,
                                  'stake': stake, 'payout': payout}, index=w.index))
    tr = pd.concat(rows).sort_index()
    tr.to_csv(OUT / 'portfolio_trades.csv', encoding='utf-8-sig')

    for label, sub in [('IS(検証期間)', tr[tr.index < best_cut]), ('OOS(フォワード)', tr[tr.index >= best_cut])]:
        m = sub['pnl'].resample('ME').sum()
        m = m[m != 0]
        cum = sub['pnl'].cumsum()
        dd = (cum - cum.cummax()).min()
        print(f'\n=== {label} {sub.index.min():%Y-%m-%d} .. {sub.index.max():%Y-%m-%d} ===')
        print(f'月平均 {m.mean():+,.0f}円  月中央値 {m.median():+,.0f}円  勝ち月 {(m>0).mean()*100:.0f}%  最大DD {dd:+,.0f}円')
        per = sub.groupby('strategy').agg(n=('win', 'size'), wr=('win', lambda x: x.mean() * 100),
                                          pnl=('pnl', 'sum'))
        print(per.round(2).to_string())
    print('\nOOS月次:')
    print(tr[tr.index >= best_cut]['pnl'].resample('ME').sum().round(0).to_string())


if __name__ == '__main__':
    main()
