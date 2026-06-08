# -*- coding: utf-8 -*-
"""
portfolio_patterns.py — 全EA(v7/v4/E5/E-Mon)を並べ、複数のポートフォリオ・パターンを実数で評価。

エッジ(全てYahoo日足10年・同一ハーネス。E-Mon=株価指数月曜=本ブランチP2と同一/7stt2と独立収束):
  v7   円月曜(EURJPY/GBPJPY/USDJPY)         STRONG-LEAD
  v4   FX日足 k>=4合議 逆張り                 ADOPT(単体最強)
  E5   多資産 月次TSMOM(金/株指/暗号)         STRONG-LEAD(最弱・無相関衛星)
  E-Mon 株価指数月曜(US500/NAS100/GER40)      STRONG-LEAD(新・v7と+0.22の別分散源)

評価法(公平): 各成分の月次リターンを単位ボラ化→重みで合成→**合成maxDDが−6%になるよう線形スケール**し、
  その時の 年率 / Sharpe(スケール不変) / Calmar / 最悪月 を出す(docs/52「年率@−6%」と同じ土俵)。
  2口座並走は資本を均等分割した合算系列で評価(別口座/別業者で相関0.28の分散効果を見る)。
出力: research/results/portfolio_patterns.json。シミュレーション・配当抜き指数・最終確証はデモで。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_edge_search as P, p2_portfolio_validate as V

HERE=os.path.dirname(os.path.abspath(__file__))

def m_from_w(w):
    s=pd.Series(w.values,index=w.index.to_timestamp()); return s.groupby(s.index.to_period("M")).sum()

def components():
    _,legs,_=P.build_p1()                 # raw monthly: v7, v4, e5
    emon=m_from_w(V.basket_weekly(["US500","NAS100","GER40"]))
    df=pd.concat([legs["v7"].rename("v7"),legs["v4"].rename("v4"),
                  legs["e5"].rename("E5"),emon.rename("E-Mon")],axis=1).dropna()
    # 各成分を現実的な月次ボラ1%に正規化(複利が壊れない・相対リスク寄与の土台)
    unit=df/df.std()*0.01
    return df, unit

def stats_at_dd6(series):
    s=series.dropna()
    eq=(1+s).cumprod(); mdd=((eq-eq.cummax())/eq.cummax()).min()
    if mdd==0: return None
    k=0.06/abs(mdd)                       # maxDD を−6%に線形スケール
    ss=s*k
    ann=(1+ss.mean())**12-1
    sh=s.mean()/s.std()*np.sqrt(12) if s.std()>0 else 0
    return dict(sharpe=round(float(sh),2), ann_at6_pct=round(float(ann)*100,1),
                calmar=round(float(ann)/0.06,2), worst_month_pct=round(float(ss.min())*100,1))

def blend(unit, w):
    """w=dict成分→重み。単位ボラ成分を重み付き合算(重みは相対リスク寄与の目安)。"""
    cols=[unit[k]*v for k,v in w.items() if v!=0]
    return sum(cols)

def main():
    df, unit = components()
    print("成分 月次相関(10年):"); print(df.corr().round(2).to_string()); print()

    # ===== 単一口座パターン(1口座に複数EA) =====
    singles={
      "S0 現状A (v7:v4:E5=40:40:20)":           {"v7":.40,"v4":.40,"E5":.20,"E-Mon":0},
      "S1 4種・均整 (25/35/15/25) ★推奨":         {"v7":.25,"v4":.35,"E5":.15,"E-Mon":.25},
      "S2 4種・効率重視(v4厚 20/45/10/25)":        {"v7":.20,"v4":.45,"E5":.10,"E-Mon":.25},
      "S3 4種・分散最大(等加重 25/25/25/25)":       {"v7":.25,"v4":.25,"E5":.25,"E-Mon":.25},
      "S4 並行核のみ B (E-Mon:E5=65:35)":         {"v7":0,"v4":0,"E5":.35,"E-Mon":.65},
      "S5 並行・効率版 (E-Mon:v4:E5=45:40:15)":    {"v7":0,"v4":.40,"E5":.15,"E-Mon":.45},
    }
    out={"corr":df.corr().round(3).to_dict(),"singles":{},"parallel":{}}
    print("【単一口座パターン】(maxDD−6%に揃えた年率)")
    print(f"  {'パターン':40s} Sharpe  年率@-6%  Calmar  最悪月")
    for name,w in singles.items():
        st=stats_at_dd6(blend(unit,w)); out["singles"][name]=st
        print(f"  {name:40s} {st['sharpe']:5}  {st['ann_at6_pct']:6}%  {st['calmar']:5}  {st['worst_month_pct']:5}%")

    # ===== 2口座並走パターン(別口座/別業者・資本均等) =====
    def acct(w):
        b=blend(unit,w); return b/b.std()*0.01  # 各口座を月次ボラ1%に揃える(同リスク口座)
    pairs={
      "P-α A‖B (現状 ‖ E-Mon+E5)":      (singles["S0 現状A (v7:v4:E5=40:40:20)"], singles["S4 並行核のみ B (E-Mon:E5=65:35)"]),
      "P-β A‖B+ (現状 ‖ E-Mon+v4+E5)":  (singles["S0 現状A (v7:v4:E5=40:40:20)"], singles["S5 並行・効率版 (E-Mon:v4:E5=45:40:15)"]),
      "P-γ FX口座 ‖ 株指口座 (v7+v4 ‖ E-Mon+E5)": ({"v7":.5,"v4":.5,"E5":0,"E-Mon":0}, {"v7":0,"v4":0,"E5":.35,"E-Mon":.65}),
    }
    print("\n【2口座並走パターン】(別口座/別業者・資本均等・各口座を同リスク化)")
    print(f"  {'パターン':44s} Sharpe  年率@-6%  Calmar  最悪月  口座間相関")
    for name,(wa,wb) in pairs.items():
        a=acct(wa); b=acct(wb)
        j=pd.concat([a.rename('a'),b.rename('b')],axis=1).dropna()
        comb=0.5*j['a']+0.5*j['b']
        st=stats_at_dd6(comb); corr=round(float(j['a'].corr(j['b'])),2)
        out["parallel"][name]=dict(**st,acct_corr=corr)
        print(f"  {name:44s} {st['sharpe']:5}  {st['ann_at6_pct']:6}%  {st['calmar']:5}  {st['worst_month_pct']:5}%   {corr}")

    with open(os.path.join(HERE,"results","portfolio_patterns.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("\n保存: research/results/portfolio_patterns.json")

if __name__=="__main__":
    main()
