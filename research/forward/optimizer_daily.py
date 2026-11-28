# -*- coding: utf-8 -*-
"""docs/349 §9c: 毎朝の「最適解の再探索」。config/portfolio_current.json(現行設定)を起点に、1 パラメータずつ動かした近傍を同時シミュレーション(forward/portfolio_sim)で評価し、
現行より「期待 +5% 以上 かつ −1σ が悪化しない(−2 万まで)」候補があれば表示する。採用は人の「切替」の後(この script は config を書き換えない)。
近傍: 全体 keep {−0.05, +0.05}・k {×0.5, ×1.5}・pay_frac {0.5 ↔ 1.0}、口座ごとに 評価倍率 {×0.75, ×1.25}・資金化後倍率 {×0.75, ×1.25}・k {−0.5, +0.5}(証拠金上限 名目 ≤ 16 倍)。
使い方: cd research && python3 forward/optimizer_daily.py [N]   出力: results/optimizer_daily_latest.json と標準出力の表"""
import os, sys, json, copy, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
from forward.portfolio_sim import run_portfolio, summarize, legs
import numpy as np
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000; MAX_GROSS = 16.0
import datetime as _dt; SEED = int(_dt.date.today().strftime("%Y%m%d"))  # 日替わりの乱数種(同じ朝の近傍比較は共通乱数)。固定種だと毎朝同じ結果になり再現の意味が無い
cfg = json.load(open("config/portfolio_current.json", encoding="utf-8"))
def gross(spec): return sum(spec.values())
def variants(cfg):
    out = []
    g = cfg["global"]
    for d in (-0.05, 0.05):
        c = copy.deepcopy(cfg); c["global"]["keep"] = round(max(0.0, g["keep"] + d), 2); out.append((f"全体 keep {g['keep']:.2f} → {c['global']['keep']:.2f}", c))
    for m in (0.5, 1.5):
        c = copy.deepcopy(cfg); c["global"]["k"] = round(g["k"] * m, 2); out.append((f"全体 k {g['k']} → {c['global']['k']}", c))
    c = copy.deepcopy(cfg); c["global"]["pay_frac"] = 0.5 if g.get("pay_frac", 1.0) >= 1.0 else 1.0; out.append((f"全体 pay_frac → {c['global']['pay_frac']}", c))
    for i, a in enumerate(cfg["accounts"]):
        if not a.get("active", True): continue
        for key in ("eval", "funded"):
            if key == "eval" and a.get("funded_now"): continue
            for m in (0.75, 1.25):
                c = copy.deepcopy(cfg); spec = {k: round(w * m, 3) for k, w in a[key].items()}
                if gross(spec) * (1 + c["accounts"][i].get("k", g["k"])) > MAX_GROSS * 1.0 and key == "funded": continue
                c["accounts"][i][key] = spec; out.append((f"{a['name']} {key} ×{m}", c))
        for d in (-0.5, 0.5):
            k0 = a.get("k", g["k"]); k1 = round(max(0.0, k0 + d), 2)
            if gross(a["funded"]) * (1 + k1) > MAX_GROSS: continue
            c = copy.deepcopy(cfg); c["accounts"][i]["k"] = k1; out.append((f"{a['name']} k {k0} → {k1}", c))
    return out
base_s = summarize(run_portfolio(cfg, N=N, seed=SEED), "current"); rows = [base_s]
print(f"現行: 期待 {base_s['mean']:.0f} 万 | −1σ {base_s['p16']:.0f} | 中央 {base_s['p50']:.0f} | 0 の確率 {base_s['p0']*100:.0f}%   (N={N}・近傍 {len(variants(cfg))} 件)")
for nm, c in variants(cfg):
    s = summarize(run_portfolio(c, N=N, seed=SEED), nm); s["improved"] = bool(s["mean"] >= base_s["mean"] * 1.05 and s["p16"] >= base_s["p16"] - 2); rows.append(s)
    if s["improved"]: print(f"  ○ {nm:<34} 期待 {s['mean']:.0f} 万(+{(s['mean']/base_s['mean']-1)*100:.0f}%) | −1σ {s['p16']:.0f} | 中央 {s['p50']:.0f}")
imp = [r for r in rows[1:] if r["improved"]]
print("改善候補: " + (", ".join(r["label"] for r in sorted(imp, key=lambda r: -r["mean"])[:5]) if imp else "なし(現行が近傍で最適)"))
json.dump(dict(date=str(dt.date.today()), N=N, current=base_s, rows=rows), open("results/optimizer_daily_latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
