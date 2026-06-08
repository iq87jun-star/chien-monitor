# -*- coding: utf-8 -*-
"""
p2_vs_p1_combined.py — P1(v7+v4+E5) と P2(株価指数 週初ロング) の併用分散効果を定量化。

「別ポートフォリオを並列運用する」ことの価値=低相関ゆえの Sharpe 改善・DD 縮小 を、
月次ボラを共通(1.0%)に正規化した公平比較で出す(スケール不変)。数字は実行出力のみ。
出力: research/results/p2_vs_p1_combined.json。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_edge_search as P, p2_portfolio_validate as V

HERE=os.path.dirname(os.path.abspath(__file__))

def m_from_w(w):
    s=pd.Series(w.values,index=w.index.to_timestamp()); return s.groupby(s.index.to_period("M")).sum()
def scale(s,tv=0.01):
    s=s.dropna(); return s/s.std()*tv if s.std()>0 else s
def sh(m): return round(float(m.mean()/m.std()*np.sqrt(12)),2) if m.std()>0 else 0.0
def dd(m): eq=(1+m).cumprod(); return round(float(((eq-eq.cummax())/eq.cummax()).min())*100,1)
def ann(m): return round(float((1+m.mean())**12-1)*100,2)

def main():
    eqm=m_from_w(V.basket_weekly(["US500","NAS100","GER40"]))   # P2核 月次
    P1,legs,_=P.build_p1()
    j=pd.concat([scale(P1).rename("p1"),scale(eqm).rename("p2")],axis=1).dropna()
    comb=0.5*j["p1"]+0.5*j["p2"]
    cor=round(float(j["p1"].corr(j["p2"])),3)
    out=dict(
        note="月次ボラ1.0%に正規化した公平比較(スケール不変)。生の絶対DDはサイジング依存。",
        n_months=int(len(j)), corr_P1_P2=cor,
        P1_alone =dict(sharpe=sh(j["p1"]),ann_pct=ann(j["p1"]),maxDD_pct=dd(j["p1"])),
        P2_alone =dict(sharpe=sh(j["p2"]),ann_pct=ann(j["p2"]),maxDD_pct=dd(j["p2"])),
        combined_50_50=dict(sharpe=sh(comb),ann_pct=ann(comb),maxDD_pct=dd(comb)),
        sharpe_lift=round(sh(comb)/sh(j["p1"]),2) if sh(j["p1"]) else None,
    )
    print(json.dumps(out,ensure_ascii=False,indent=2))
    with open(os.path.join(HERE,"results","p2_vs_p1_combined.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("\n保存: research/results/p2_vs_p1_combined.json")

if __name__=="__main__":
    main()
