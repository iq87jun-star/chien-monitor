# -*- coding: utf-8 -*-
"""2026-11-10 ユーザー「倍率を検証しましょう」: トパーズ 6104739 の評価中倍率(InpMult 8.0)を現在地から検証する(docs/416)。
現在地: 11/10 08:04 JST に含み益の玉を手動決済 → 残高 37,583,822(初期 3,500 万比 +7.38%)・P1 目標 8% まで +0.58%・有効額 37,493,648。
格子: InpMult m = 3〜12(EA は Mon4 と指数の名目を同じ InpMult で掛けるので全レグを m/8 倍)。資金化後のレグ(Mon4 ×4・指数 ×0.5)は固定。
指標: account_cards.mc(現状規則・日次 −2.8% ガードで頭打ち・N=6000)の 失格 / 出金到達 / 資金化の中央月 / 30 か月期待(万円)と、
ガード無しの 5 年日次(2021-10〜)の 最悪日 / ≤−2.8% 日数/年 / ≤−5% 日数/年(Fintokei スイングの日次限度 = 残高基準 5%)/ |日次| ≥ 4.4%(11/9 の設計どおりの日)の日数/年。
使い方: cd research && python3 -W ignore queue/mult_verify_6104739_20261110.py   出力: results/mult_verify_6104739_20261110.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, mc, ea_book, daily_window, EA_LEGS = (ns[k] for k in ("cfg", "mc", "ea_book", "daily_window", "EA_LEGS")); acc_id = ns["ns"]["acc_id"]
A = [a for a in cfg["accounts"] if acc_id(a["name"]) == "6104739"][0]; EL = EA_LEGS["6104739"]
BAL0 = 35_000_000; BAL = 37_583_822; EQ = 37_493_648; E0 = EQ / BAL0
TODAY = 0.044   # 11/9 の設計どおり(指数 1 本)の日次 ≈ +155 万 / 3,526 万
rows = []
for m in (3, 4, 5, 6, 7, 8, 10, 12):
    b = copy.deepcopy(A); b["eval"] = {k: v * m / 8 for k, v in EL["eval"].items()}; b["funded"] = dict(EL["funded"]); b["e0"] = E0
    r = mc(b)
    rd = daily_window(ea_book(b["eval"], 0.0)); yrs = (rd.index[-1] - rd.index[0]).days / 365.25
    rows.append(dict(mult=m, p_reach=r["p_reach"], p_fail=r["p_fail"], p_pay=r["p_pay"], t_med=r.get("t_med"), c12_med=r["c12_med"] / 1e4, c30_mean=r["c30_mean"] / 1e4,
                     worst_day=rd.min(), best_day=rd.max(), d_guard=(rd <= -0.028).sum() / yrs, d_limit=(rd <= -0.05).sum() / yrs, d_big=(rd.abs() >= TODAY).sum() / yrs,
                     mean_m=rd.mean() * 21, sd_d=rd.std(), rule_scale_m=round(0.05 / abs(rd.min()) * m, 2)))
    print(f"m={m:>2}  失格 {r['p_fail']:.1%} 到達 {r['p_pay']:.1%} 資金化中央 {r.get('t_med')} 30m期待 {r['c30_mean']/1e4:,.0f}万 | 最悪日 {rd.min():+.1%} ≤-2.8% {rows[-1]['d_guard']:.1f}/年 ≤-5% {rows[-1]['d_limit']:.1f}/年 |日|≥4.4% {rows[-1]['d_big']:.1f}/年 規約揃え m={rows[-1]['rule_scale_m']}")
pd.DataFrame(rows).to_csv("results/mult_verify_6104739_20261110.csv", index=False)
print("keys:", sorted(r.keys()))

# ---- P1 までの短期(週単位ブートストラップ): 現在地 e0 → 目標 1.08 / 床 0.90。週次リターン = 5 年の週合計(ガード: 日次 −2.8% で頭打ち)から復元抽出 ----
print("\n[P1 まで +%.2f%%] 週次ブートストラップ N=20000(日次はガードで −2.8%% 頭打ち)" % ((1.08 - E0) * 100))
rng = np.random.default_rng(7); out = []
for m in (3, 4, 5, 6, 7, 8, 10, 12):
    lg = {k: v * m / 8 for k, v in EL["eval"].items()}; rd = daily_window(ea_book(lg, 0.0)).clip(lower=-0.028)
    wk = rd.groupby(pd.Grouper(freq="W-FRI")).sum(); wk = wk[wk != 0].values
    N_ = 20000; e = np.full(N_, E0); done = np.zeros(N_, int); t = np.zeros(N_, int)   # done: 1=到達 -1=失格
    for w in range(1, 27):
        act = done == 0; e[act] *= 1 + rng.choice(wk, act.sum()); t[act] = w
        done[act & (e >= 1.08)] = 1; done[act & (e <= 0.90)] = -1
    p1 = (done == 1).mean(); pf = (done == -1).mean(); tw = t[done == 1]
    r4 = ((done == 1) & (t <= 4)).mean(); r1 = ((done == 1) & (t <= 1)).mean()
    out.append(dict(mult=m, p_week_up=(wk >= 1.08 - E0).mean(), p_week_guard=(wk <= -0.028).mean(), p1_in1w=r1, p1_in4w=r4, p1_in26w=p1, fail_before_p1=pf, t_med_w=float(np.median(tw)) if len(tw) else None))
    print(f"m={m:>2}  来週で到達 {r1:.0%}  4 週以内 {r4:.0%}  26 週以内 {p1:.0%}  先に失格 {pf:.1%}  中央 {np.median(tw):.0f} 週 | 週 ≥+{(1.08-E0)*100:.2f}% の割合 {out[-1]['p_week_up']:.0%}・週 ≤−2.8% {out[-1]['p_week_guard']:.0%}")
pd.DataFrame(out).to_csv("results/mult_verify_6104739_20261110_p1.csv", index=False)
