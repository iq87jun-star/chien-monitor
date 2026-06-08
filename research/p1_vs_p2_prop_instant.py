# -*- coding: utf-8 -*-
"""
p1_vs_p2_prop_instant.py — 現運用 P1(v7+v4+E5) と 第2 P2(株価指数 週初ロング) を
                           【同一リスク倍率】で PROP / INSTANT 両ルールで比較。

「同一リスク倍率」の定義(公平): 両ポートフォリオの月次リターンを**同じ目標ボラ(1x=月次1.5%)**に
正規化し、同じ倍率 L を掛ける。→ Lが同じなら両者は同じリスク。差は「エッジの質・テール形状・相関」由来。

ルール:
  PROP   : 初期10万, 静的−10%で失格(DQ), +8%到達で合格(PASS), 上限60ヶ月。
           ※日次−4%は月次粒度では近似不可→注記(両戦略とも低日次ボラでdocs上DQ寄与≈0)。
  INSTANT: 初期10万, ピークから−10%トレーリングで失格(DQ), 無目標, 期間12ヶ月。
           測定=12ヶ月DQ率 / 中央12ヶ月リターン / p95最悪maxDD。
比較対象: P1単体 / P2単体 /（参考）P1+P2 50:50併用（同じ総リスク=各レッグ0.5×で合算1x）。

月次ブロックブートストラップ(block=3ヶ月, 自己相関保持)。出力: results/p1_vs_p2_prop_instant.json。
注意: シミュレーション。指数=配当抜き・CFD実コスト未計上。将来約定を保証しない。誇張しない。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_edge_search as P, p2_portfolio_validate as V

HERE=os.path.dirname(os.path.abspath(__file__))
TARGET_VOL=0.015          # 1x = 月次ボラ1.5%(年率~5.2%)。両PFを同一に正規化=「同じリスク倍率」の土台
SEED=20260608
N=6000; BLOCK=3
PROP_CAP=60; PROP_TARGET=0.08; PROP_FLOOR=-0.10
INST_MONTHS=12; INST_TRAIL=-0.10

def m_from_w(w):
    s=pd.Series(w.values,index=w.index.to_timestamp()); return s.groupby(s.index.to_period("M")).sum()

def norm(s, tv=TARGET_VOL):
    s=s.dropna(); return (s/s.std()*tv).values if s.std()>0 else s.values

def streams():
    """P1合成 / P2 / 併用 を 同一目標ボラ(1x) の月次リターン配列で返す(共通月で揃える)。"""
    P1z,legs,_=P.build_p1()                       # 0.4z(v7)+0.4z(v4)+0.2z(e5)
    eqm=m_from_w(V.basket_weekly(["US500","NAS100","GER40"]))
    j=pd.concat([P1z.rename("p1"),eqm.rename("p2")],axis=1).dropna()
    p1=j["p1"]/j["p1"].std()*TARGET_VOL
    p2=j["p2"]/j["p2"].std()*TARGET_VOL
    comb=0.5*p1+0.5*p2                              # 同じ総リスクではない→併用は別途同ボラ化
    comb=comb/comb.std()*TARGET_VOL                 # 併用も1xに正規化(同一リスク倍率で比較)
    return dict(P1=p1.values, P2=p2.values, **{"P1+P2":comb.values}), len(j)

def boot_path(arr, L, rng, months):
    out=[]; n=len(arr)
    while len(out)<months:
        st=rng.integers(0,max(1,n-BLOCK)); out.extend(arr[st:st+BLOCK]*L)
    return np.array(out[:months])

def sim_prop(arr,L,rng):
    p=boot_path(arr,L,rng,PROP_CAP); eq=1.0; peak=1.0; mdd=0.0
    for i,r in enumerate(p):
        eq*=(1+r); peak=max(peak,eq); mdd=min(mdd,eq/peak-1.0)
        if eq-1.0<=PROP_FLOOR: return ("DQ",i+1,mdd)
        if eq-1.0>=PROP_TARGET: return ("PASS",i+1,mdd)
    return ("TIMEOUT",PROP_CAP,mdd)

def sim_instant(arr,L,rng):
    p=boot_path(arr,L,rng,INST_MONTHS); eq=1.0; peak=1.0; mdd=0.0; dq=False
    for r in p:
        eq*=(1+r); peak=max(peak,eq); dd=eq/peak-1.0; mdd=min(mdd,dd)
        if dd<=INST_TRAIL: dq=True
    return (eq-1.0, mdd, dq)

def run():
    S,nm=streams()
    print(f"共通月数={nm}  1x=月次ボラ{TARGET_VOL*100:.1f}%  PROP(静的−10%/+8%) / INSTANT(−10%トレ/12ヶ月)\n")
    Ls=[0.5,1.0,1.5,2.0]; out={"target_vol":TARGET_VOL,"n_months":nm,"prop":{},"instant":{}}
    for name,arr in S.items():
        out["prop"][name]={}; out["instant"][name]={}
        print(f"================ {name} ================")
        print(" PROP:   L     合格%   失格%  時間切%  中央到達  p95maxDD | INSTANT: 12moDQ%  中央年率  p5最悪  p95maxDD")
        for L in Ls:
            rng=np.random.default_rng(SEED)
            res=[sim_prop(arr,L,rng) for _ in range(N)]
            npass=sum(1 for r in res if r[0]=="PASS"); ndq=sum(1 for r in res if r[0]=="DQ")
            nto=sum(1 for r in res if r[0]=="TIMEOUT")
            passmo=[r[1] for r in res if r[0]=="PASS"]; mdd=[r[2] for r in res]
            rng=np.random.default_rng(SEED+1)
            ires=[sim_instant(arr,L,rng) for _ in range(N)]
            irets=np.array([r[0] for r in ires]); imdd=np.array([r[1] for r in ires])
            idq=np.mean([r[2] for r in ires])*100
            pr=dict(pass_pct=round(100*npass/N,1),dq_pct=round(100*ndq/N,1),to_pct=round(100*nto/N,1),
                    med_pass_mo=int(np.median(passmo)) if passmo else None,p95_maxDD=round(float(np.percentile(mdd,5))*100,1))
            ins=dict(dq12_pct=round(float(idq),1),med_ann_pct=round(float(np.median(irets))*100,1),
                     p5_worst_pct=round(float(np.percentile(irets,5))*100,1),p95_maxDD=round(float(np.percentile(imdd,5))*100,1))
            out["prop"][name][L]=pr; out["instant"][name][L]=ins
            print(f"        {L:<4} {pr['pass_pct']:6}  {pr['dq_pct']:5}  {pr['to_pct']:6}  "
                  f"{str(pr['med_pass_mo']):>6}mo  {pr['p95_maxDD']:6}% |          {ins['dq12_pct']:5}   "
                  f"{ins['med_ann_pct']:6}%  {ins['p5_worst_pct']:6}%  {ins['p95_maxDD']:6}%")
        print()
    with open(os.path.join(HERE,"results","p1_vs_p2_prop_instant.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("保存: research/results/p1_vs_p2_prop_instant.json")

if __name__=="__main__":
    run()
