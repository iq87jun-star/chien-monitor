# -*- coding: utf-8 -*-
"""docs/244 Q224(2026-11-15 登録「登録して実行」): 順番を逆にした選別。記録済みのセル(標準形式の results/q*.csv)を母集団に、
第 1 段 = 前窓(2016-01〜2021-09)の +月数の二項検定だけで選ぶ((a) p < 0.05/母集団、(b) p の小さい順に上位 1%)。
第 2 段 = 2021-10 以降(探索 + OOS 合算)の +月数の二項検定 p < 0.05/K かつ 探索の平均 > 0 かつ OOS の平均 > 0。
診断: 前窓の +月率と探索の +月率の順位相関(全体・家族別)。
使い方: cd research && python3 -W ignore queue/q224_reverse_order_screen.py <累積セル数>   出力: results/q224_reverse_order_screen.csv・_families.csv"""
import sys, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
from scipy import stats as sps
cum = int(sys.argv[1]); rows = []
for f in sorted(glob.glob("results/q*.csv")):
    if "q224" in f: continue
    try: d = pd.read_csv(f)
    except Exception: continue
    if {"pre_rate", "pre_n", "is_plus", "is_n", "is_rate", "is_mean_bps", "oos_plus", "oos_n", "oos_mean_bps", "family", "symbol", "spec"} <= set(d.columns): rows.append(d.assign(src=os.path.basename(f)))
A = pd.concat(rows, ignore_index=True); A = A[(A.pre_n >= 48) & (A.is_n >= 24) & (A.oos_n >= 6)].copy(); U = len(A)
A["pre_plus"] = (A.pre_rate * A.pre_n).round().astype(int); A["p_pre"] = [float(sps.binom.sf(k - 1, n, 0.5)) for k, n in zip(A.pre_plus, A.pre_n)]
A["post_plus"] = (A.is_plus + A.oos_plus).astype(int); A["post_n"] = (A.is_n + A.oos_n).astype(int); A["post_rate"] = (A.post_plus / A.post_n).round(3); A["p_post"] = [float(sps.binom.sf(k - 1, n, 0.5)) for k, n in zip(A.post_plus, A.post_n)]
strict = A[A.p_pre < 0.05 / U]; thr = A.p_pre.sort_values().iloc[max(int(np.ceil(U * 0.01)) - 1, 0)]; S = A[A.p_pre <= thr].copy(); K = len(S)
S["stage2"] = (S.p_post < 0.05 / K) & (S.is_mean_bps > 0) & (S.oos_mean_bps > 0); S = S.sort_values("p_pre")
S[["src", "family", "symbol", "spec", "pre_n", "pre_rate", "p_pre", "is_rate", "is_mean_bps", "oos_mean_bps", "post_n", "post_rate", "p_post", "passed", "stage2"]].to_csv("results/q224_reverse_order_screen.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_colwidth", 44); pd.set_option("display.max_rows", 200)
print(f"Q224: 母集団 {U} 本 / 第 1 段 (a) 厳密(p < {0.05 / U:.2e})= {len(strict)} 本 / (b) 上位 1%(p ≤ {thr:.2e})= K {K} 本 / 第 2 段(p < {0.05 / K:.2e}・探索と OOS の平均 > 0)通過 = {int(S.stage2.sum())} 本 / cum_before={cum} cum_after={cum + K}")
print(S[["src", "family", "symbol", "spec", "pre_rate", "p_pre", "is_rate", "is_mean_bps", "oos_mean_bps", "post_rate", "p_post", "stage2"]].to_string(index=False))
rho, pv = sps.spearmanr(A.pre_rate, A.is_rate); rho2, pv2 = sps.spearmanr(A.pre_rate, A.post_rate)
print(f"\n診断: 前窓の +月率 と 探索の +月率 の順位相関 {rho:+.3f}(p {pv:.1e})/ 2021-10 以降合算との順位相関 {rho2:+.3f}(p {pv2:.1e})・n {U}")
q = pd.qcut(A.pre_rate.rank(method="first"), 5, labels=["下位 20%", "20〜40%", "40〜60%", "60〜80%", "上位 20%"]); print("前窓の +月率の 5 分位ごと: 前窓の平均 / 2021-10 以降の +月率の平均 / 探索の平均 bps の中央値 / OOS の平均 bps の中央値"); print(A.groupby(q).agg(pre=("pre_rate", "mean"), post=("post_rate", "mean"), is_bps=("is_mean_bps", "median"), oos_bps=("oos_mean_bps", "median"), n=("pre_rate", "size")).round(3).to_string())
G = []
for fam, x in A.groupby("family"):
    if len(x) >= 20: r, p = sps.spearmanr(x.pre_rate, x.post_rate); G.append(dict(family=fam, n=len(x), pre_med=round(float(x.pre_rate.median()), 3), post_med=round(float(x.post_rate.median()), 3), rho=round(float(r), 3), p=round(float(p), 4)))
G = pd.DataFrame(G).sort_values("n", ascending=False); G.to_csv("results/q224_reverse_order_screen_families.csv", index=False); print("\n家族別(20 本以上)の順位相関:"); print(G.to_string(index=False))
