# -*- coding: utf-8 -*-
"""docs/302: 3 本ポートフォリオを「直近 12 ヶ月の成績上位 3 セル」で 3 ヶ月毎に入れ替えた場合(ウォークフォワード)。
宇宙 = docs/290 の 47 セル(ロール込み/抜き)。選抜指標 = 直近 12m Sharpe または 12m リターン。重み = 直近 12m 逆ボラ。評価 2022-10〜2026-08(16 四半期)。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
src=open("leg_5y_scorecard.py",encoding="utf-8").read().split("rows = []")[0]
ns={"__name__":"leg5y","__file__":os.path.join(HERE,"leg_5y_scorecard.py")}; exec(compile(src,"leg5y","exec"),ns); L=ns["L"]
S={f"{f} {s}":x for (f,s,u),x in L.items()}
def stats(x):
    x=x[x!=0] if False else x; eq=(1+x).cumprod(); mon=x.groupby(pd.PeriodIndex(x.index,freq="M")).apply(lambda q:(1+q).prod()-1); yrs=(x.index[-1]-x.index[0]).days/365.25
    return dict(cagr=round(((eq.iloc[-1])**(1/yrs)-1)*100,1),dd=round((eq/eq.cummax()-1).min()*100,1),wd=round(x.min()*100,2),wm=round(mon.min()*100,1),pos=f"{int((mon>0).sum())}/{int((mon!=0).sum())}",
                sh=round(x.mean()/x.std()*np.sqrt(252),2),yrs=" ".join(f"{y}:{((1+x[x.index.year==y]).prod()-1)*100:+.1f}" for y in range(2022,2027)))
Q=pd.date_range("2022-10-01","2026-07-01",freq="QS"); END=pd.Timestamp("2026-08-31")
def rotate(univ,metric,k=3):
    out=[]; picks=[]
    for q0 in Q:
        q1=min(q0+pd.DateOffset(months=3)-pd.Timedelta(days=1),END); lb0=q0-pd.DateOffset(months=12)
        sc={}
        for n in univ:
            h=S[n][(S[n].index>=lb0)&(S[n].index<q0)]
            if h.std()<=0: continue
            sc[n]=(h.mean()/h.std()*np.sqrt(252)) if metric=="sharpe" else (1+h).prod()-1
        top=sorted(sc,key=sc.get,reverse=True)[:k]
        iv=np.array([1/S[n][(S[n].index>=lb0)&(S[n].index<q0)].std() for n in top]); w=iv/iv.sum()
        seg=sum(wi*S[n][(S[n].index>=q0)&(S[n].index<=q1)] for wi,n in zip(w,top)); out.append(seg); picks.append((q0.strftime("%Y-%m"),top,np.round(w,2).tolist(),round(((1+seg).prod()-1)*100,2)))
    return pd.concat(out),picks
A=lambda: 0.12*S["Hold XAUUSD"]+0.632*S["Mon GBPJPY"]+0.248*S["Mon NAS100"]
res={}
for uname,univ in [("47 セル(ロール込み)",list(S)),("42 セル(ロール抜き)",[n for n in S if not n.startswith("Roll")])]:
    for metric in ("sharpe","return"):
        p,picks=rotate(univ,metric); res[(uname,metric)]=(p,picks)
        print(f"\n=== {uname} / 選抜=直近12m {metric} 上位3 / 四半期入替 ===  評価 {p.index.min().date()}〜{p.index.max().date()}")
        print("  ",stats(p))
        for q,top,w,r in picks: print(f"   {q}: {top} w={w} 四半期 {r:+.2f}%")
base=A(); base=base[(base.index>=Q[0])&(base.index<=END)]
print("\n=== 参考: 固定 A(XAU .12 / Mon GBPJPY .632 / Mon NAS100 .248)同期間 ===\n  ",stats(base))
# 入替ポートフォリオ vs 固定 A の相関と、両者を半々にした場合
for key,(p,_) in res.items():
    both=pd.concat([p,base],axis=1).fillna(0); print(f"  corr(入替 {key[0][:2]}/{key[1]}, 固定A)={both.corr().iloc[0,1]:.2f}  半々: {stats(0.5*both.iloc[:,0]+0.5*both.iloc[:,1])}")
