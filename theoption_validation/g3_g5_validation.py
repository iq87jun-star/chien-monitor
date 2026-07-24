#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ザオプション v4.0 採用20戦略への追加検証 (2026-07-23)
  G3相当: ポジション循環シフト順列検定 (シグナル↔リターン整合の破壊, 200本)
  G5相当: 年抜きJackknife (leave-one-year-out で補正後Edgeが正を維持するか)
  多重性再補正: Phase16拡張後の実効探索数 M=3200 で Bonferroni を引き直し

データ: Dukascopy 1時間足 (UTC) -> JST(+9h) 変換。
取引抽出ロジックは 2026-05-25 のオリジナル実装 (Notion「1000パターン検証 実装コード」) を忠実に再現。
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

DATA_DIR = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad/hourly')
OUT_DIR = Path('/tmp/claude-0/-home-user-chien-monitor/2d8625e1-7e1e-5833-a930-e549c6238e73/scratchpad')

SPREAD_DECAY_CORR = 2.0  # pp
N_SHIFTS = 200
# Phase16でペアを16に拡張済み → 実効探索数を保守的に 16ペア×20エントリー×5曜日×2方向
M_EFF = 16 * 20 * 5 * 2  # 3200
ALPHA_EFF = 0.05 / M_EFF

WEEKDAYS = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4}

# 採用20戦略 (theoption_phase16pairs_tier_S_A.csv より)
# (pair, weekday, entry_h, judgment_h, next_day, payout, tier, ref_n, ref_wr)
STRATEGIES = [
    ('EURGBP', 'Thu', 7, 11, False, 1.90, 'S', 541, 70.98),
    ('USDCHF', 'Mon', 7, 11, False, 1.90, 'S', 539, 66.79),
    ('EURGBP', 'Wed', 7, 11, False, 1.90, 'S', 540, 65.93),
    ('GBPJPY', 'Mon', 7, 14, False, 1.95, 'S', 537, 62.94),
    ('AUDJPY', 'Mon', 7, 2, True, 1.95, 'A', 537, 62.76),
    ('EURGBP', 'Fri', 7, 14, False, 1.95, 'A', 541, 62.48),
    ('USDCHF', 'Wed', 7, 14, False, 1.95, 'A', 540, 62.41),
    ('GBPUSD', 'Mon', 7, 14, False, 1.95, 'S', 538, 62.27),
    ('NZDJPY', 'Mon', 7, 14, False, 1.95, 'S', 537, 62.20),
    ('EURGBP', 'Tue', 7, 11, False, 1.90, 'A', 541, 63.22),
    ('CADJPY', 'Mon', 7, 14, False, 1.95, 'S', 538, 61.71),
    ('EURJPY', 'Mon', 7, 2, True, 1.95, 'A', 537, 60.52),
    ('GBPJPY', 'Tue', 7, 14, False, 1.95, 'S', 541, 60.07),
    ('AUDJPY', 'Mon', 10, 2, True, 1.95, 'A', 538, 59.85),
    ('USDCHF', 'Fri', 7, 11, False, 1.90, 'A', 541, 61.18),
    ('AUDUSD', 'Mon', 7, 14, False, 1.95, 'A', 539, 59.37),
    ('EURGBP', 'Thu', 8, 11, False, 1.90, 'A', 541, 60.63),
    ('AUDJPY', 'Mon', 11, 2, True, 1.95, 'A', 538, 59.11),
    ('CHFJPY', 'Mon', 7, 2, True, 1.95, 'A', 536, 58.96),
    ('USDCHF', 'Tue', 7, 11, False, 1.90, 'A', 541, 59.70),
]


def load_hourly(pair):
    df = pd.read_csv(DATA_DIR / f'{pair}_hourly.csv')
    df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=9)  # UTC -> JST
    return df.set_index('datetime').sort_index()[['Open', 'Close']]


def all_day_trades(df_h1, entry_hour, judgment_hour, next_day):
    """全曜日ぶんの取引系列 (オリジナルの get_trades_to_judgment と同一ロジック、曜日フィルタなし)"""
    entries = df_h1[df_h1.index.hour == entry_hour]
    close_by_time = df_h1['Close']
    rows = []
    for entry_time, entry_open in entries['Open'].items():
        exit_date = entry_time.normalize() + pd.Timedelta(days=1 if next_day else 0)
        exit_time = exit_date + pd.Timedelta(hours=judgment_hour)
        if exit_time <= entry_time:
            continue
        exit_bar = exit_time - pd.Timedelta(hours=1)
        if exit_bar not in close_by_time.index:
            continue
        rows.append((entry_time, entry_time.dayofweek, entry_time.year,
                     close_by_time.loc[exit_bar] > entry_open))
    out = pd.DataFrame(rows, columns=['entry_dt', 'weekday', 'year', 'high_win'])
    return out.sort_values('entry_dt').reset_index(drop=True)


def perm_test_circular(all_trades, wd_num, observed_wr):
    """G3: 曜日選択マスクを取引系列上で循環シフトし、整合破壊後のWR分布と比較"""
    wins = all_trades['high_win'].to_numpy().astype(float)
    mask = (all_trades['weekday'] == wd_num).to_numpy()
    n = len(wins)
    shifts = np.unique(np.linspace(1, n - 1, N_SHIFTS).astype(int))
    null_wrs = np.array([np.roll(wins, k)[mask].mean() * 100 for k in shifts])
    p = (1 + (null_wrs >= observed_wr).sum()) / (1 + len(shifts))
    return p, null_wrs.mean()


def main():
    cache = {}
    results = []
    for pair, wd, eh, jh, nd, payout, tier, ref_n, ref_wr in STRATEGIES:
        key = (pair, eh, jh, nd)
        if key not in cache:
            if pair not in cache.setdefault('_df', {}):
                cache['_df'][pair] = load_hourly(pair)
            cache[key] = all_day_trades(cache['_df'][pair], eh, jh, nd)
        allt = cache[key]
        wd_num = WEEKDAYS[wd]
        sel = allt[allt['weekday'] == wd_num]
        n, wins = len(sel), int(sel['high_win'].sum())
        wr = wins / n * 100
        be = 100 / payout
        edge_adj = wr - SPREAD_DECAY_CORR - be
        p_binom = stats.binom.sf(wins - 1, n, be / 100)

        # G3 循環シフト
        perm_p, null_mean = perm_test_circular(allt, wd_num, wr)
        drift_wr = allt['high_win'].mean() * 100  # 全曜日ベースライン (ドリフト成分)

        # G5 年抜きJackknife
        jk = []
        for yr in sorted(sel['year'].unique()):
            rest = sel[sel['year'] != yr]
            if len(rest) < 30:
                continue
            jk_wr = rest['high_win'].mean() * 100
            jk.append((yr, jk_wr - SPREAD_DECAY_CORR - be))
        jk_min_year, jk_min_edge = min(jk, key=lambda t: t[1])

        g3_pass = perm_p < 0.05
        g5_pass = jk_min_edge > 0
        bonf_eff_pass = p_binom < ALPHA_EFF
        grade = 'STRONG' if (g3_pass and g5_pass and bonf_eff_pass) else (
            'LEAD' if (g5_pass and bonf_eff_pass) else 'FAIL')

        results.append(dict(
            pair=pair, weekday=wd, entry_h=eh,
            judgment=('02:00翌日' if nd else f'{jh:02d}:00当日'),
            payout=payout, tier=tier,
            n=n, ref_n=ref_n, wr=round(wr, 2), ref_wr=ref_wr,
            edge_adj=round(edge_adj, 2),
            drift_wr_allday=round(drift_wr, 2),
            perm_p=round(perm_p, 4), null_mean_wr=round(null_mean, 2),
            jk_min_edge=round(jk_min_edge, 2), jk_worst_year=jk_min_year,
            p_binom=f'{p_binom:.2e}', bonf_eff_pass=bonf_eff_pass,
            g3_pass=g3_pass, g5_pass=g5_pass, grade=grade,
        ))
        r = results[-1]
        print(f"{pair} {wd} {eh:02d}時→{r['judgment']}: n={n}(参照{ref_n}) WR={wr:.2f}%(参照{ref_wr}) "
              f"Edge={edge_adj:+.2f}pp | 全曜日WR={drift_wr:.2f}% perm_p={perm_p:.4f} "
              f"| JK最低Edge={jk_min_edge:+.2f}pp(除外{jk_min_year}) | Bonf(M=3200)={'PASS' if bonf_eff_pass else 'FAIL'} "
              f"=> {grade}")

    df = pd.DataFrame(results)
    df.to_csv(OUT_DIR / 'theoption_g3_g5_results.csv', index=False, encoding='utf-8-sig')
    print('\n=== サマリー ===')
    print(f"α_eff = 0.05/{M_EFF} = {ALPHA_EFF:.2e}")
    for g in ['STRONG', 'LEAD', 'FAIL']:
        sub = df[df['grade'] == g]
        print(f"{g}: {len(sub)}件 " + ', '.join(f"{r.pair}/{r.weekday}/{r.entry_h}時" for r in sub.itertuples()))


if __name__ == '__main__':
    main()
