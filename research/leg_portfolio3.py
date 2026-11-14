# -*- coding: utf-8 -*-
"""docs/301: 47 セル(docs/290)から 3 本ポートフォリオを総当たり。逆ボラ加重(Σw=1)・5 年 2021-10〜2026-08・日次ガード無し。
候補 = 5 年 Sharpe ≥ 0.6 のセル。宇宙 A = ロール抜き(全業者)、B = ロール込み(swap-free 業者のみ)。"""
import os, sys, itertools, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
src=open("leg_5y_scorecard.py",encoding="utf-8").read().split("rows = []")[0]
ns={"__name__":"leg5y","__file__":os.path.join(HERE,"leg_5y_scorecard.py")}; exec(compile(src,"leg5y","exec"),ns); L=ns["L"]; A=ns["A"]; B=ns["B"]
S={}
for (f,s,u),x in L.items():
    x=x[(x.index>=A)&(x.index<=B)]
    if x.std()>0 and x.mean()/x.std()*np.sqrt(252)>=0.6: S[f"{f} {s}"]=x
print("候補セル:",len(S),sorted(S))
def stats(x):
    eq=(1+x).cumprod(); mon=x.groupby(pd.PeriodIndex(x.index,freq="M")).apply(lambda q:(1+q).prod()-1)
    yrs=(x.index[-1]-x.index[0]).days/365.25; cum=eq.iloc[-1]-1
    return dict(cagr=round(((1+cum)**(1/yrs)-1)*100,1),cum=round(cum*100,1),dd=round((eq/eq.cummax()-1).min()*100,1),wm=round(mon.min()*100,1),wd=round(x.min()*100,2),
                pos=f"{int((mon>0).sum())}/{int((mon!=0).sum())}",sh=round(x.mean()/x.std()*np.sqrt(252),2),
                yrs=" ".join(f"{y}:{((1+x[x.index.year==y]).prod()-1)*100:+.1f}" for y in range(2022,2027)))
rows=[]
for combo in itertools.combinations(sorted(S),3):
    xs=[S[c] for c in combo]; iv=np.array([1/x.std() for x in xs]); w=iv/iv.sum()
    p=sum(wi*x for wi,x in zip(w,xs)); st=stats(p)
    corr=pd.concat(xs,axis=1).corr().values; mc=max(corr[0,1],corr[0,2],corr[1,2])
    rows.append(dict(legs=" + ".join(combo),w=" / ".join(f"{v:.2f}" for v in w),maxcorr=round(mc,2),roll=any(c.startswith("Roll") for c in combo),**st))
R=pd.DataFrame(rows); R["calmar"]=(R["cagr"]/R["dd"].abs()).round(2); R.to_csv("results/leg_portfolio3.csv",index=False)
pd.set_option("display.width",300); pd.set_option("display.max_colwidth",60)
cols=["legs","w","maxcorr","cagr","dd","wm","wd","pos","sh","calmar","yrs"]
for name,sub in [("A) ロール抜き(全業者)",R[~R.roll]),("B) ロール込み(swap-free 業者)",R[R.roll])]:
    print(f"\n=== {name}: Sharpe 上位 12 ==="); print(sub.sort_values("sh",ascending=False).head(12)[cols].to_string(index=False))
    print(f"--- {name}: 相関 ≤0.3 のうち Sharpe 上位 8 ---"); print(sub[sub.maxcorr<=0.3].sort_values("sh",ascending=False).head(8)[cols].to_string(index=False))
    print(f"--- {name}: Calmar 上位 6 ---"); print(sub.sort_values("calmar",ascending=False).head(6)[cols].to_string(index=False))
