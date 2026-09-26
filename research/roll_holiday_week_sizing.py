# -*- coding: utf-8 -*-
"""docs/307: JP 祝日を含む週の水曜ロールに倍率を上乗せした場合(サイズ配分の検討・プロトコル外の MC)。ロール 5 本合成(金利差門・往復 3pip・Dukascopy H1)。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,"queue"))
from q_common import *; from q_cal import *
from q20_wed_swap_carry import rate_series
ROLL=["USDJPY","EURJPY","GBPJPY","AUDJPY","CADJPY"]
def leg(sym):
    df=load(sym); o=df["open"]; days=pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry=rate_series(sym[:3],days)-rate_series("JPY",days)
    t=o.index[(o.index.dayofweek==2)&(o.index.hour==20)]; cy=carry.reindex(t.normalize()).values; t=t[(cy>=1.0)&~np.isnan(cy)]
    r=trades(sym,t,o.reindex(t).values,-np.ones(len(t)),o.reindex(t+pd.Timedelta(hours=4)).values); r.index=r.index.normalize(); return r/5.0
R5=None
for s in ROLL: r=leg(s); R5=r if R5 is None else R5.add(r,fill_value=0)
R5=R5[R5.index>=pd.Timestamp("2022-01-01")]
hol=pd.Series([in_week(t,JPHOL) for t in R5.index],index=R5.index)
def st(x,a,b):
    x=x[(x.index>=a)&(x.index<=b)]; eq=(1+x).cumprod(); yrs=(x.index[-1]-x.index[0]).days/365.25; wk=x
    return dict(n=len(x),mean_bps=round(float(x.mean())*1e4,2),sharpe=round(float(x.mean()/x.std()*np.sqrt(52)),2) if x.std()>0 else 0,cagr=round(((eq.iloc[-1])**(1/yrs)-1)*100,2),dd=round(float((eq/eq.cummax()-1).min())*100,2),worst=round(float(x.min())*100,2),plus=round(float((x>0).mean())*100,1))
print(f"祝日週の水曜: {int(hol.sum())} / {len(hol)} ({hol.mean()*100:.0f}%)")
for nm,a,b in [("IS 2022-01〜2024-12",pd.Timestamp("2022-01-01"),IS1),("OOS 2025-01〜",OOS0,END),("全期間",pd.Timestamp("2022-01-01"),END)]:
    print(f"\n[{nm}] 祝日週 {st(R5[hol],a,b)} | 通常週 {st(R5[~hol],a,b)}")
print("\n== 倍率配分(平均露出=1 に固定: 祝日週 ×k・通常週 ×(1−f·k)/(1−f))と、露出を増やす版(祝日週 ×k・通常週 ×1) ==")
f=float(hol.mean())
rows=[]
for k in (1.0,1.5,2.0,2.5,3.0):
    iso=R5*np.where(hol,k,(1-f*k)/(1-f)); add=R5*np.where(hol,k,1.0)
    for lab,x in (("等露出",iso),("上乗せ",add)):
        rows.append(dict(k=k,方式=lab,**{f"{w}_{m}":v for w,a,b in [("IS",pd.Timestamp("2022-01-01"),IS1),("OOS",OOS0,END),("5y",pd.Timestamp("2022-01-01"),END)] for m,v in st(x,a,b).items() if m in ("sharpe","cagr","dd","worst")}))
pd.set_option("display.width",300); print(pd.DataFrame(rows).to_string(index=False))
