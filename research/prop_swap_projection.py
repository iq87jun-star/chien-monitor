# -*- coding: utf-8 -*-
"""
prop_swap_projection.py — PROPでポートフォリオを 3種(v7+v4+E5)→4種(+E-Mon) に入れ替えた後の
                          (1)チャレンジ通過の想定到達月 と (2)資金化後の期待収益額 をMC推計。

校正: 現状3種・PROP 3.0x が docs/46(中央3ヶ月でP1+P2突破・失格8%)に一致するようスケールを合わせ、
      同一スケール(=同じDD/リスク)で4種(加重S1・同DD)を評価。数字は盛らない。
2フェーズ: P1 +8% / P2 +5% / 各フェーズ 初期比 -10% で失格 / 時間無制限(上限36ヶ月)。
資金化後: 通過後12ヶ月運用→ 期待年率(税前・分配前) と $口座×分配率での年間ペイアウト。
注意: 月次ブロックBS。日次-4%は月次粒度で未モデル(低日次ボラで寄与小)。Yahoo再構築・配当抜き。デモで実測必須。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portfolio_patterns as PP

HERE=os.path.dirname(os.path.abspath(__file__))
SEED=20260608; N=20000; BLOCK=3; CAPM=36
P1T=0.08; P2T=0.05; FLOOR=-0.10

df,unit=PP.components()
def blend(w): return sum(unit[k]*v for k,v in w.items() if v)
S0={'v7':.40,'v4':.40,'E5':.20,'E-Mon':0}      # 現状3種
S1={'v7':.25,'v4':.35,'E5':.15,'E-Mon':.25}    # 4種・加重(同DD)
def mdd(s): s=pd.Series(s); eq=(1+s).cumprod(); return float(((eq-eq.cummax())/eq.cummax()).min())

def boot(arr,rng,n):
    out=[]; m=len(arr)
    while len(out)<n:
        st=rng.integers(0,max(1,m-BLOCK)); out.extend(arr[st:st+BLOCK])
    return out[:n]

def run_phase(arr,rng,target):
    eq=1.0; mo=0
    seq=boot(arr,rng,CAPM)
    for r in seq:
        eq*=(1+r); mo+=1
        if eq-1.0<=FLOOR: return ("DQ",mo)
        if eq-1.0>=target: return ("PASS",mo)
    return ("TIMEOUT",mo)

def challenge(arr,rng):
    s1=run_phase(arr,rng,P1T)
    if s1[0]!="PASS": return (s1[0], s1[1])
    s2=run_phase(arr,rng,P2T)
    if s2[0]!="PASS": return (s2[0], s1[1]+s2[1])
    return ("FUNDED", s1[1]+s2[1])

def funded_year(arr,rng):
    eq=1.0; seq=boot(arr,rng,12)
    for r in seq:
        eq*=(1+r)
        if eq-1.0<=FLOOR: return (eq-1.0, True)   # 資金化口座を失う
    return (eq-1.0, False)

def evaluate(arr,label):
    rng=np.random.default_rng(SEED)
    res=[challenge(arr,rng) for _ in range(N)]
    funded=[m for (o,m) in res if o=="FUNDED"]; dq=sum(1 for (o,_) in res if o=="DQ")
    rng2=np.random.default_rng(SEED+1)
    fy=[funded_year(arr,rng2) for _ in range(N)]
    fret=np.array([r for (r,_) in fy]); flost=np.mean([l for (_,l) in fy])
    return dict(label=label,
        funded_pct=round(100*len(funded)/N,1), dq_pct=round(100*dq/N,1),
        med_months=int(np.median(funded)) if funded else None,
        mean_months=round(float(np.mean(funded)),1) if funded else None,
        p25=int(np.percentile(funded,25)) if funded else None,
        p75=int(np.percentile(funded,75)) if funded else None,
        funded_yr_mean_pct=round(float(np.mean(fret))*100,1),
        funded_yr_med_pct=round(float(np.median(fret))*100,1),
        funded_loss_pct=round(float(flost)*100,1),
        monthly_mean_pct=round(float(np.mean(arr))*100,3), maxDD_unscaled=round(mdd(arr)*100,1))

# --- スケール校正: 現状3種が docs/46(中央3ヶ月 / 失格~8%)に合う scale を探索 ---
b0=blend(S0); b1=blend(S1)
print("scale校正(現状3種 → 中央3ヶ月/失格~8%目標):")
best=None
for scale in [0.020,0.025,0.030,0.035,0.040,0.045,0.050]:
    r=evaluate(b0.values*scale/ (b0.std()) , f"S0 x{scale}")  # 月次ボラ=scale
    print(f"  月次vol{scale*100:.1f}%: 中央{r['med_months']}ヶ月 失格{r['dq_pct']}% 資金化{r['funded_pct']}% (年率素{(((1+r['monthly_mean_pct']/100)**12-1)*100):.1f}%)")
    if r['med_months'] is not None and best is None and r['med_months']<=3 and r['dq_pct']<=12:
        best=scale
SC = best if best else 0.035
print(f"\n採用scale(月次vol)= {SC*100:.1f}%  ← 現状3種PROP3.0xの校正値\n")

def at(series,scale): return series.values/series.std()*scale
print("="*70)
r0=evaluate(at(b0,SC),"現状3種(v7+v4+E5)")
r1=evaluate(at(b1,SC),"4種・加重(+E-Mon, 同DD)")
for r in (r0,r1):
    print(f"\n[{r['label']}]")
    print(f"  資金化(P1+P2突破)到達: 中央 {r['med_months']}ヶ月 / 平均 {r['mean_months']}ヶ月 (四分位 {r['p25']}–{r['p75']}ヶ月)")
    print(f"  最終資金化率(無制限): {r['funded_pct']}%  / 途中失格: {r['dq_pct']}%")
    print(f"  資金化後1年: 期待年率(素) 平均 {r['funded_yr_mean_pct']}% / 中央 {r['funded_yr_med_pct']}% / 口座喪失 {r['funded_loss_pct']}%")

# 期待収益額(資金化後・年間ペイアウト) $口座×分配率
print("\n--- 資金化後の年間ペイアウト目安(期待年率×口座×分配率) ---")
for size in (50000,100000,200000):
    for split in (0.80,0.90):
        amt0=r0['funded_yr_mean_pct']/100*size*split
        amt1=r1['funded_yr_mean_pct']/100*size*split
        print(f"  ${size:>7,} 分配{int(split*100)}%: 現状3種≈${amt0:,.0f}/年  4種≈${amt1:,.0f}/年 (¥は×150換算で 3種≈¥{amt0*150:,.0f} / 4種≈¥{amt1*150:,.0f})")

out=dict(scale_monthly_vol=SC, current3=r0, swap4=r1)
with open(os.path.join(HERE,"results","prop_swap_projection.json"),"w") as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print("\n保存: research/results/prop_swap_projection.json")
