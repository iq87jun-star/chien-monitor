# -*- coding: utf-8 -*-
"""docs/322 §5h Q120(工学・セル 0): 先物口座(Builder 150K・EOD トレーリング MLL $4,500・日次ソフト停止 $2,500)で、残余 MLL(= 残高 − 損失限度)に応じて枚数を落とす規則が
評価通過率・sim 失格率・期待手取りをどう変えるかを MC で比較する。基準 = 固定 5/2/5(名目 ≈ $451k・docs/336 §16)。
規則 A: 残余 < 50% で半分、< 25% で休み。規則 B: 残余 < 70% で半分、< 35% で休み。規則 C: 残余に比例(名目 = 基準 × 残余/MLL、上限 1)。
使い方: cd research && python3 queue/q120_dynamic_contracts.py"""
import sys
from q_common import *
from q114_mon_index_intraday import shot
PX = {"US500": 7860 * 5, "NAS100": 31110 * 2, "US30": 51930 * 0.5}; Q = {"US500": 5, "NAS100": 2, "US30": 5}
S = pd.concat({k: shot(k, 13, 20) for k in PX}, axis=1).dropna(); S = S[S.index >= "2018-01-01"]
N = sum(PX[k] * Q[k] for k in PX); r = (sum(S[k] * PX[k] * Q[k] / N for k in PX) + 2.5e-4).values
rng = np.random.default_rng(7)
def scale(rule, b, floor, mll):
    rem = (b - floor) / mll
    if rule == "固定": return 1.0
    if rule == "A": return 0.0 if rem < 0.25 else (0.5 if rem < 0.5 else 1.0)
    if rule == "B": return 0.0 if rem < 0.35 else (0.5 if rem < 0.7 else 1.0)
    if rule == "C": return float(min(1.0, max(0.0, rem)))
def evaluation(rule, n=20000, target=9000, mll=4500, dll=2500, max_weeks=104):
    res = []
    for _ in range(n):
        b = hi = 0.0; floor = -mll; ok = None; wk = 0
        while wk < max_weeks:
            wk += 1; s = scale(rule, b, floor, mll); x = max(rng.choice(r) * N * s, -dll); b += x
            if b <= floor: ok = False; break
            hi = max(hi, b); floor = max(floor, min(hi - mll, 100.0))
            if b >= target: ok = True; break
        res.append((ok, wk))
    o = pd.DataFrame(res, columns=["ok", "wk"]); return float((o.ok == True).mean()), float((o.ok == False).mean()), float(o[o.ok == True].wk.median() if (o.ok == True).any() else 0)
def sim_funded(rule, n=20000, mll=4500, dll=2500, buf=4600, pmin=4500, pcap=4500, npay=5, max_weeks=156):
    res = []
    for _ in range(n):
        b = hi = 0.0; floor = -mll; paid = 0.0; k = 0; wk = 0; breach = False; locked = False
        while wk < max_weeks and k < npay:
            wk += 1; s = scale(rule, b, floor, mll); b += max(rng.choice(r) * N * s, -dll)
            if b <= floor: breach = True; break
            hi = max(hi, b)
            if not locked:
                floor = max(floor, hi - mll)
                if hi >= buf: locked = True; floor = 100.0
            if locked and b - buf >= pmin: p = min(b - buf, pcap); paid += p; b -= p; k += 1
        res.append((breach, paid, k, wk))
    o = pd.DataFrame(res, columns=["breach", "paid", "k", "wk"]); d = o[o.k == npay]
    return float(o.breach.mean()), float(o.paid.mean() * 0.8), float(len(d) / len(o)), float(d.wk.median() if len(d) else 0)
def live(rule, n=20000, mll=4500, dll=2500, reserve=12000, years=1):
    res = []
    for _ in range(n):
        b = hi = 0.0; floor = -mll; paid = 0.0; breach = False
        for wk in range(52 * years):
            s = scale(rule, b, floor, mll); b += max(rng.choice(r) * N * s, -dll)
            if b <= floor: breach = True; break
            hi = max(hi, b); floor = min(max(floor, hi - mll), 0.0)
            if b > reserve: paid += b - reserve; b = reserve
        res.append((breach, paid))
    o = pd.DataFrame(res, columns=["breach", "paid"]); return float(o.breach.mean()), float(o.paid.mean() * 0.8)
rows = []
for rule in ("固定", "A", "B", "C"):
    ep, ef, ew = evaluation(rule); sb, sp, sl, sw = sim_funded(rule); lb, lp = live(rule)
    rows.append(dict(rule=rule, eval_pass=round(ep, 3), eval_fail=round(ef, 3), eval_weeks=ew, sim_breach=round(sb, 3), sim_net=round(sp), sim_live=round(sl, 3), sim_weeks=sw, live_breach_1y=round(lb, 3), live_net_1y=round(lp)))
D = pd.DataFrame(rows); pd.set_option("display.width", 250); print(f"名目 ${N:,.0f} 週平均 ${r.mean()*N:,.0f} 週σ ${r.std()*N:,.0f}\n" + D.to_string(index=False)); D.to_csv("results/q120_dynamic_contracts.csv", index=False)
