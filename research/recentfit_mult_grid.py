# -*- coding: utf-8 -*-
"""
recentfit_mult_grid.py — RecentFit構成(docs/175)の成績表示+リスク倍率グリッド。
ユーザー要望(2026-07-30)「新ポートフォリオの成績を表示 / リスク倍率を上げたものも」。
方法: recentfit_screen.py の凍結窓・セル・重みを逐語再利用し、倍率4.8〜12.0の
月次成績・年次成績・チャレンジMC(直近/全期間の両バウンド)を横並び計測。
選抜のやり直しはしない(docs/174 §3の事前固定ルールを変更しない)。
出力: results/recentfit_mult_grid.json → docs/175 追補
"""
import os, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, HERE)

from recentfit_screen import (mon_cell, v4_cell, hold_cell, win, worst_stats,
                              mc_challenge, W12_0, W6_0, SEED, sha256s)

WEIGHTS = {"Mon_GBPJPY": 0.348, "Mon_AUDJPY": 0.299, "v4_USDJPY": 0.283, "Hold_JP225": 0.070}
MULTS = [4.8, 6.0, 7.2, 9.6, 12.0]


def build_composite():
    cells = {"Mon_GBPJPY": mon_cell("GBPJPY"), "Mon_AUDJPY": mon_cell("AUDJPY"),
             "v4_USDJPY": v4_cell("USDJPY"), "Hold_JP225": hold_cell("JP225")}
    idx = sorted(set().union(*[set(s.index) for s in cells.values()]))
    comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in WEIGHTS.items():
        comp = comp.add(cells[k].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
    return comp


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({str(k): float((1 + s[mk == k]).prod() - 1) * 100 for k in mk.unique()}).sort_index()


def yearly(s):
    yk = pd.DatetimeIndex(s.index).year
    return pd.Series({int(y): float((1 + s[yk == y]).prod() - 1) * 100 for y in sorted(set(yk))})


def main():
    comp = build_composite()
    comp12 = win(comp, W12_0)
    out = dict(meta=dict(weights=WEIGHTS, seed=SEED, mults=MULTS,
                         note="選抜・重みはdocs/175凍結値のまま。倍率のみ可変。"
                              "直近=楽観バウンド/全期間=悲観バウンド。ガードで日次−4%クリップ済み",
                         inputs=sha256s()),
               grid={}, monthly_recent={}, yearly_full={})
    print(f"{'mult':>5} {'直近12m累積':>10} {'最悪日':>7} {'月中DD':>7} | 直近: 資金化/失格/中央日 | 全期間: 資金化/失格/中央日")
    for m in MULTS:
        s12 = comp12 * m
        wd, wdd = worst_stats(s12)
        cum = float((1 + np.clip(s12, -0.04, None)).prod() - 1) * 100
        mc_r = mc_challenge(comp12, m, np.random.default_rng(SEED))
        mc_f = mc_challenge(comp, m, np.random.default_rng(SEED))
        out["grid"][str(m)] = dict(recent_cum_12m=round(cum, 1),
                                   recent_worst_day=round(wd * 100, 2),
                                   recent_worst_intramonth_dd=round(wdd * 100, 2),
                                   recent12m=mc_r, full_history=mc_f)
        out["monthly_recent"][str(m)] = {k: round(v, 2) for k, v in
                                         monthly(np.clip(s12, -0.04, None)).items()}
        out["yearly_full"][str(m)] = {str(k): round(v, 1) for k, v in
                                      yearly(np.clip(comp * m, -0.04, None)).items()}
        print(f"{m:>5} {cum:>9.1f}% {wd*100:>6.2f}% {wdd*100:>6.2f}% | "
              f"{mc_r['funded']:>5.1f}%/{mc_r['fail']:>4.1f}%/{mc_r['funded_days_med']}日 | "
              f"{mc_f['funded']:>5.1f}%/{mc_f['fail']:>4.1f}%/{mc_f['funded_days_med']}日")
    path = os.path.join(HERE, "results", "recentfit_mult_grid.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
