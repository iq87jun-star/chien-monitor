#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase2 F3: ポートフォリオ配分最適化 (2026-07-24)
事前登録: prereg_phase2_entry_families.md (探索なし・多重性なし)

1. 統合ポートフォリオ10戦略のトレードレベルP&L再構築 → 追補3数値と照合
2. 日次P&L相関行列
3. 定常ブロック・ブートストラップ(平均ブロック20営業日, B=2000本@最終評価)で10年maxDD分布を推定
4. 「ブートストラップ95%点DD ≤ 30万円」制約下で月次期待値を最大化する配分を探索
5. ストレス: ペイアウト劣化・Edge一律-2pp
6. オプション: F1合格のETH土曜スリーブ追加時の効果
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path('/tmp/claude-0/-home-user-chien-monitor/bb965c91-9b36-5899-9568-61e61c2aee05/scratchpad/hourly')
OUT = Path(__file__).parent
rng = np.random.default_rng(20260724)

def load(pair):
    df = pd.read_csv(DATA / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)
    return df.set_index('datetime').sort_index()

# (name, pair, entry_h, weekdays, judge, direction, 停止月, payout, 現行掛金円)
STRATS = [
    ('EURGBP_D_7-11H',  'EURGBP',  7,  [0,1,2,3,4], ('h', 11), 'HIGH', [],           1.90, 14000),
    ('GBPJPY_M_7-14H',  'GBPJPY',  7,  [0],         ('h', 14), 'HIGH', [],           1.95, 14000),
    ('AUDJPY_M_7-n2H',  'AUDJPY',  7,  [0],         ('n', 2),  'HIGH', [],           1.95, 14000),
    ('GBPUSD_M_7-14H',  'GBPUSD',  7,  [0],         ('h', 14), 'HIGH', [],           1.95, 13000),
    ('NZDJPY_M_7-14H',  'NZDJPY',  7,  [0],         ('h', 14), 'HIGH', [],           1.95, 13000),
    ('CADJPY_M_7-14H',  'CADJPY',  7,  [0],         ('h', 14), 'HIGH', [],           1.95, 12000),
    ('EURJPY_M_7-n6H',  'EURJPY',  7,  [0],         ('n', 6),  'HIGH', [],           1.95, 11000),
    ('USDCHF_D_7-14H',  'USDCHF',  7,  [0,1,2,3,4], ('h', 14), 'HIGH', [],           1.95,  9000),
    ('EURGBP_E_23-n6L', 'EURGBP', 23, [0,1,2,4],    ('n', 6),  'LOW',  [2,3,6,12],   1.95,  4000),
    ('EURAUD_D_10-n6L', 'EURAUD', 10, [0,1,2,3,4],  ('n', 6),  'LOW',  [],           1.95,  3000),
]
# F1合格スリーブ (オプションB用)
ETH_SLEEVE = ('ETHUSDT_S_2-n6H', 'ETHUSDT', 2, [5], ('n', 6), 'HIGH', [], 1.95, None)

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

def daily_pnl_matrix(strat_list, wr_haircut=0.0, payout_shift=0.0):
    """日次P&L行列 (per 1000円掛金)。wr_haircut: WRをppで下げる(負けをランダム化せず期待値で近似はしない
    → トレード単位で決定的に扱えないため、haircut適用時は各戦略の勝ちトレードのうち
    haircut/WR相当割合を期待値的に減算する近似を用いる)"""
    cols = {}
    for s in strat_list:
        name, pair, eh, wds, judge, direction, skip, payout, _ = s
        win = build_trades(pair, eh, wds, judge, direction, skip)
        po = payout + payout_shift
        pnl = np.where(win.to_numpy(), (po - 1.0) * 1000, -1000.0)
        if wr_haircut > 0:
            # 期待値ベースの近似: 全トレードから haircut% × (勝額+負額) を均等控除
            pnl = pnl - wr_haircut / 100.0 * (po * 1000)
        d = pd.Series(pnl, index=win.index.normalize()).groupby(level=0).sum()
        cols[name] = d
    D = pd.DataFrame(cols).fillna(0.0)
    return D

def max_drawdown(cum):
    peak = np.maximum.accumulate(cum, axis=-1)
    return (peak - cum).max(axis=-1)

def gen_bootstrap_indices(n_days, B, mean_block=20):
    """定常ブートストラップのインデックス集合"""
    idx = np.empty((B, n_days), dtype=np.int32)
    for b in range(B):
        out = np.empty(n_days, dtype=np.int32)
        i = 0
        while i < n_days:
            start = rng.integers(0, n_days)
            L = min(rng.geometric(1 / mean_block), n_days - i)
            seq = (np.arange(start, start + L)) % n_days
            out[i:i + L] = seq
            i += L
        idx[b] = out
    return idx

def eval_weights(D_vals, idx, W):
    """W: (n_strat, n_cand) per-1000円ウェイト。戻り: (mean_annual, hist_maxDD, p95_boot_maxDD)"""
    pnl = D_vals @ W                     # (days, cand)
    years = D_vals.shape[0] / 260.7
    mean_annual = pnl.sum(axis=0) / years
    hist_dd = max_drawdown(np.cumsum(pnl, axis=0).T)
    boot_dd = np.empty((idx.shape[0], W.shape[1]))
    for b in range(idx.shape[0]):
        boot_dd[b] = max_drawdown(np.cumsum(pnl[idx[b]], axis=0).T)
    return mean_annual, hist_dd, np.percentile(boot_dd, 95, axis=0), np.percentile(boot_dd, 50, axis=0)

# ---- 1. 再構築と照合 ----
D = daily_pnl_matrix(STRATS)
names = list(D.columns)
cur_stake = np.array([s[8] for s in STRATS], float)
w_cur = cur_stake / 1000.0
pnl_cur = D.to_numpy() @ w_cur
months = pd.Series(pnl_cur, index=D.index).resample('ME').sum()
active = months[months.ne(0)]
cum = np.cumsum(pnl_cur)
hist_dd_cur = float(max_drawdown(cum[None, :])[0])
yearly = pd.Series(pnl_cur, index=D.index).resample('YE').sum()
print("=== 1. 現行配分の再構築照合 (追補3: 月平均+147,856 / maxDD-296,019 / 勝ち月86%) ===")
print(f"補正なしP&L: 月平均 {active.mean():+,.0f}円 / 歴史的maxDD -{hist_dd_cur:,.0f}円 / 勝ち月 {(active>0).mean()*100:.0f}% / 負け年 {(yearly<0).sum()}")
Dh = daily_pnl_matrix(STRATS, wr_haircut=2.0)
pnl_h = Dh.to_numpy() @ w_cur
mo_h = pd.Series(pnl_h, index=Dh.index).resample('ME').sum()
act_h = mo_h[mo_h.ne(0)]
dd_h = float(max_drawdown(np.cumsum(pnl_h)[None, :])[0])
print(f"-2pp補正込みP&L: 月平均 {act_h.mean():+,.0f}円 / 歴史的maxDD -{dd_h:,.0f}円 / 勝ち月 {(act_h>0).mean()*100:.0f}%")

# ---- 2. 相関行列 ----
corr = D.corr()
corr.to_csv(OUT / 'phase2_f3_daily_corr.csv')
hi = [(names[i], names[j], corr.iloc[i, j]) for i in range(len(names)) for j in range(i + 1, len(names)) if abs(corr.iloc[i, j]) > 0.15]
print("\n=== 2. 日次P&L相関 (|r|>0.15のペア) ===")
for a, b, r in sorted(hi, key=lambda x: -abs(x[2])):
    print(f"  {a} × {b}: r={r:+.2f}")

# ---- 3-4. ブートストラップ最適化 ----
D_vals = D.to_numpy()
n_days, n_s = D_vals.shape
idx_search = gen_bootstrap_indices(n_days, B=200)
idx_final = gen_bootstrap_indices(n_days, B=2000)

# 候補: 現行 + Edge比例近傍Dirichlet + 一様Dirichlet
edges = np.array([9.86, 9.63, 9.60, 8.88, 8.75, 8.30, 7.51, 6.23, 3.0, 2.0])  # 概算Edge(重み種)
base = edges / edges.sum()
cands = [w_cur / w_cur.sum()]
cands += list(rng.dirichlet(base * 60, 700))
cands += list(rng.dirichlet(np.ones(n_s) * 3, 700))
W = np.array(cands).T  # 相対ウェイト (n_s, n_cand)

# 各候補をP95(bootDD)=300kにスケールして年次期待値を比較
ma, hdd, p95, p50 = eval_weights(D_vals, idx_search, W)
scale = 300000.0 / p95
annual_at_budget = ma * scale
order = np.argsort(-annual_at_budget)
top = order[:40]

# 上位40候補をB=2000で精密評価
ma2, hdd2, p95_2, p50_2 = eval_weights(D_vals, idx_final, W[:, top])
scale2 = 300000.0 / p95_2
annual2 = ma2 * scale2
best_i = int(np.argmax(annual2))
w_best = W[:, top[best_i]] * scale2[best_i] * 1000  # 円建て掛金
w_best = np.clip(np.round(w_best / 1000) * 1000, 0, 20000)  # 1000円刻み・上限20k

# 現行配分(実掛金)も同じB=2000で評価
ma_c, hdd_c, p95_c, p50_c = eval_weights(D_vals, idx_final, w_cur[:, None])
scale_c = 300000.0 / p95_c[0]

# 丸め後の最良配分を最終評価
w_fin = w_best / 1000.0
ma_f, hdd_f, p95_f, p50_f = eval_weights(D_vals, idx_final, w_fin[:, None])
pnl_f = D_vals @ w_fin
mo_f = pd.Series(pnl_f, index=D.index).resample('ME').sum()
act_f = mo_f[mo_f.ne(0)]
yr_f = pd.Series(pnl_f, index=D.index).resample('YE').sum()

print("\n=== 3. ブートストラップDD評価 (B=2000, 平均ブロック20日) ===")
print(f"現行配分(計{cur_stake.sum():,.0f}円): 歴史的maxDD -{hdd_c[0]:,.0f} / bootDD中央値 -{p50_c[0]:,.0f} / bootDD 95%点 -{p95_c[0]:,.0f}")
print(f"→ P95 DDを30万円ちょうどに収める現行比スケール: ×{scale_c:.3f}")

print("\n=== 4. 最適化配分 (P95 bootDD ≤ 30万円制約で月次期待値最大化) ===")
for n, a, b in zip(names, cur_stake, w_best):
    print(f"  {n:18s} 現行 {a:6,.0f}円 → 提案 {b:6,.0f}円")
print(f"提案配分: 月平均 {act_f.mean():+,.0f}円 / 年間 {act_f.mean()*12:+,.0f}円 / 歴史的maxDD -{hdd_f[0]:,.0f}")
print(f"          bootDD中央値 -{p50_f[0]:,.0f} / 95%点 -{p95_f[0]:,.0f} / 勝ち月 {(act_f>0).mean()*100:.0f}% / 負け年 {(yr_f<0).sum()}")
ann_cur_same_risk = ma_c[0] * scale_c
print(f"参考: 同一リスク(P95=30万)換算の年間期待値 現行×{scale_c:.2f}: {ann_cur_same_risk:+,.0f}円 vs 提案: {ma_f[0]:+,.0f}円 (+{(ma_f[0]/ann_cur_same_risk-1)*100:.1f}%)")

# ---- 4b. アウトオブサンプル検証: 前半(2016-2021前半)で最適化→後半で評価 ----
mid_day = n_days // 2
D_tr, D_te = D_vals[:mid_day], D_vals[mid_day:]
idx_tr = gen_bootstrap_indices(mid_day, B=200)
ma_t, hdd_t, p95_t, p50_t = eval_weights(D_tr, idx_tr, W)
sc_t = 300000.0 / p95_t
ord_t = np.argsort(-(ma_t * sc_t))
w_oos = W[:, ord_t[0]] * sc_t[ord_t[0]] * 1000
w_oos = np.clip(np.round(w_oos / 1000) * 1000, 0, 20000) / 1000.0
years_te = D_te.shape[0] / 260.7
ann_oos = (D_te @ w_oos).sum() / years_te
ann_cur_te = (D_te @ w_cur).sum() / years_te * (w_oos.sum() / w_cur.sum())  # 同一総掛金に正規化
dd_oos = float(max_drawdown(np.cumsum(D_te @ w_oos)[None, :])[0])
dd_cur_te = float(max_drawdown(np.cumsum(D_te @ (w_cur * w_oos.sum() / w_cur.sum()))[None, :])[0])
print("\n=== 4b. アウトオブサンプル検証 (前半で最適化 → 後半5年で評価, 総掛金を揃えて比較) ===")
print(f"後半5年 年間期待値: 前半最適化配分 {ann_oos:+,.0f}円 vs 現行配分(同総額) {ann_cur_te:+,.0f}円 ({(ann_oos/ann_cur_te-1)*100:+.1f}%)")
print(f"後半5年 maxDD: 前半最適化 -{dd_oos:,.0f}円 vs 現行(同総額) -{dd_cur_te:,.0f}円")

# ---- 5. ストレス ----
print("\n=== 5. ストレステスト (提案配分) ===")
for label, hc, ps in [('ペイアウト-0.04 (1.90→1.86等)', 0.0, -0.04),
                      ('ペイアウト-0.08', 0.0, -0.08),
                      ('全戦略WR-2pp劣化', 2.0, 0.0),
                      ('複合: WR-2pp & ペイアウト-0.04', 2.0, -0.04)]:
    Ds = daily_pnl_matrix(STRATS, wr_haircut=hc, payout_shift=ps)
    pnl_s = Ds.to_numpy() @ w_fin
    mo_s = pd.Series(pnl_s, index=Ds.index).resample('ME').sum()
    a_s = mo_s[mo_s.ne(0)]
    dd_s = float(max_drawdown(np.cumsum(pnl_s)[None, :])[0])
    print(f"  {label}: 月平均 {a_s.mean():+,.0f}円 / maxDD -{dd_s:,.0f}円")

# ---- 6. オプションB: ETH土曜スリーブ追加 ----
D2 = daily_pnl_matrix(STRATS + [ETH_SLEEVE])
# ETHは2017-08以降のみ。FX10列は2016起点 → 共通期間で相関、配分はk=1422円/Edge1pp相当の7000円で試算
w_eth = np.append(w_fin, 7.0)
common = D2.index >= '2017-08-17'
pnl_b = D2.to_numpy() @ w_eth
mo_b = pd.Series(pnl_b, index=D2.index).resample('ME').sum()
act_b = mo_b[mo_b.ne(0)]
dd_b = float(max_drawdown(np.cumsum(pnl_b)[None, :])[0])
idx_b = gen_bootstrap_indices(int(common.sum()), B=1000)
ma_b, hdd_b, p95_b, p50_b = eval_weights(D2.to_numpy()[common], idx_b, w_eth[:, None])
corr_eth = D2.loc[common].corr()['ETHUSDT_S_2-n6H'].drop('ETHUSDT_S_2-n6H').abs().max()
print("\n=== 6. オプションB: ETH土曜2時スリーブ7,000円追加 (フォワード確認までは参考値) ===")
print(f"  月平均 {act_b.mean():+,.0f}円 / 歴史的maxDD -{dd_b:,.0f}円 / 共通期間P95 bootDD -{p95_b[0]:,.0f}円")
print(f"  既存戦略との最大|相関|: {corr_eth:.3f} (土曜取引のため実質独立)")

# 保存
res = pd.DataFrame({'strategy': names, 'current_stake': cur_stake, 'proposed_stake': w_best})
res.to_csv(OUT / 'phase2_f3_allocation.csv', index=False)
mo_f.to_frame('proposed_monthly_pnl').to_csv(OUT / 'phase2_f3_monthly_pnl.csv')
