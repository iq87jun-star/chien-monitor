# -*- coding: utf-8 -*-
"""docs/244 Q152(週次アイデア束 #2・診断・セル 0): portfolio_sim に C6 のレグ(Mon CADJPY/CHFJPY 等分・Mon GER40)を追加し、
FN 14166201 を C6(mon2 ×3.0・ger40 ×1.5・roll ×3.0)に置き換えた帳簿の期待値を現行(hold_uw ×2.22・roll ×4.5)と比較する(同じ乱数・3,000 本・12 か月)。
併せて Q136(docs/354)型の同時失格(同じ相場経路・1 年・評価段階の構成)を FN C6 で再計算する。config は書き換えない。
使い方: cd research && python3 queue/q152_portfolio_c6.py [N]"""
import os, sys, json, copy, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
from forward.portfolio_sim import run_portfolio, summarize, legs, R
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000; SEED = 152
cfg = json.load(open("config/portfolio_current.json", encoding="utf-8"))
C6 = {"mon2_cadchf": 3.0, "mon_ger40": 1.5, "roll": 3.0}
def fn(c): return [a for a in c["accounts"] if a["name"].startswith("FN 14166201")][0]
V = {"現行(FN: Hold UK100/WTI ×2.22 + Roll ×4.5)": cfg}
cA = copy.deepcopy(cfg); fn(cA)["funded"] = dict(C6); V["A: FN 資金化後のみ C6"] = cA
cB = copy.deepcopy(cfg); fn(cB)["funded"] = dict(C6); fn(cB)["eval"] = dict(C6); fn(cB)["dll"] = 0.03; V["B: FN 評価(P2)+資金化後 C6・日次 3%"] = cB
rows = []
for nm, c in V.items():
    res = run_portfolio(c, N=N, seed=SEED); s = summarize(res, nm); jpy, pct = res["per"]["FN 14166201"]
    q = lambda p: float(np.quantile(pct, p)) * 100
    rows.append(dict(variant=nm, total_mean=round(s["mean"]), total_p16=round(s["p16"]), total_p50=round(s["p50"]), total_p0=round(s["p0"] * 100), fn_mean_pct=round(pct.mean() * 100, 2), fn_mean_man=round(jpy.mean() / 1e4, 1), fn_p16=round(q(.16), 2), fn_p50=round(q(.5), 2), fn_p84=round(q(.84), 2), fn_p0=round((pct <= 0).mean() * 100)))
    print(f"{nm:<42} 合計 期待 {s['mean']:.0f} 万 | −1σ {s['p16']:.0f} | 中央 {s['p50']:.0f} | 0 の確率 {s['p0']*100:.0f}%  || FN 期待 {pct.mean()*100:.2f}%/月({jpy.mean()/1e4:.1f} 万) −1σ {q(.16):.2f} 中央 {q(.5):.2f} +1σ {q(.84):.2f} 0 の確率 {(pct<=0).mean()*100:.0f}%", flush=True)
pd.DataFrame(rows).to_csv("results/q152_portfolio_c6.csv", index=False)
# --- レグの基礎統計(10.6 年・Yahoo 日足近似・コスト後)と窓別 ---
lg = legs(); print("\nレグ別 年率 % / 年率 vol %(10.6 年 → 2021-10 以降):")
for k in ("hold_uw", "roll", "mon2_cadchf", "mon_ger40", "mon4"):
    s_ = lg[k]; x = R(s_); y = np.asarray(s_[(s_.index >= "2021-10-01") & (s_.index <= "2026-07-29")].values, float)
    print(f"  {k:<12} {x.mean()*252*100:5.1f} / {x.std()*np.sqrt(252)*100:4.1f}  →  {y.mean()*252*100:5.1f} / {y.std()*np.sqrt(252)*100:4.1f}")
# --- Q136 型の同時失格(評価段階の構成・1 年・静的床・同じ経路)---
FX = 158.0; mon4, bplan, mon3, holdxau, instG, a9, hold_uw, roll = (lg[k] for k in ("mon4", "bplan", "mon3", "holdxau", "instG", "a9", "hold_uw", "roll")); mon2, ger = lg["mon2_cadchf"], lg["mon_ger40"]
nas_spx = lg["idx"]
def acc_list(fn_series, fn_dll):
    return [("FTMO 50k 521100397 Mon4 ×6", mon4 * 6, 0.10, 0.04), ("FTMO 50k 531407058 Mon4 ×6", mon4 * 6, 0.10, 0.04), ("パール B案 ×8", bplan * 8, 0.10, 0.028),
            ("14074882 Mon3 ×4 + HoldXAU 0.4", mon3 * 4 + holdxau * 0.4, 0.10, 0.04), ("Instant G ×4", instG, 0.06, 0.04), ("1-Step EA9 ×3 + Mon4 ×2", a9 * 3 + mon4 * 2, 0.10, 0.024),
            ("宝くじ Mon4 ×10 + HoldXAU 0.9", mon4 * 10 + holdxau * 0.9, 0.095, 0.04), ("FN 14166201", fn_series, 0.10, fn_dll), ("ルビー B案 ×12", bplan * 12, 0.10, 0.028), ("トパーズ Mon4 ×8 + 指数 ×1", mon4 * 8 + nas_spx * 1.0, 0.10, 0.028)]
def joint(ACC, label):
    Rm = np.stack([R(c.clip(lower=-dll)) for nm, c, mdd, dll in ACC], axis=1); rng = np.random.default_rng(36); Nn, BLOCK, days = 20000, 5, 250
    nb = len(Rm) - BLOCK + 1; stt = rng.integers(0, nb, size=(Nn, days // BLOCK + 1)); idx = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(Nn, -1)[:, :days]
    FL = 1 - np.array([a[2] for a in ACC]); e = np.cumprod(1 + Rm[idx], axis=1); br = (e <= FL[None, None, :]).any(axis=1); k = br.sum(axis=1)
    print(f"\n{label}: 1 年内の同時失格 期待 {k.mean():.2f} 本・3 本以上 {(k>=3).mean()*100:.1f}%・5 本以上 {(k>=5).mean()*100:.1f}%・全部無事 {(k==0).mean()*100:.1f}% | FN 単独 {br[:, 7].mean()*100:.1f}%")
    return k, br
joint(acc_list(hold_uw * 2.22 + roll * 4.5, 0.04), "現行(FN Hold+Roll)"); joint(acc_list(mon2 * 3.0 + ger * 1.5 + roll * 3.0, 0.03), "FN C6(×3.0・日次 3%)")
