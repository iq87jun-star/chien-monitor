# -*- coding: utf-8 -*-
"""docs/308: 祝日系フィルター 4 本(祝日月曜・翌火曜JP祝日・豪NZ祝日・月末水曜ロール除外)を入れる前後の、口座別ロジック(配備倍率)の 5 年成績と到達 MC。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,"queue"))
from q_common import *; from q_cal import *
from q20_wed_swap_carry import rate_series
base.DATA=os.path.join(ROOT,"data_202609"); import deployed_book as db
A,B=pd.Timestamp("2021-10-01"),pd.Timestamp("2026-08-31"); BD=pd.bdate_range(A,B)
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
def mon(sym,new):
    m=base.mon_cell(sym)
    if not new or not sym.endswith("JPY"): return on_bd(m)
    keep=[not is_jp_holiday(t) and not is_jp_holiday(t+pd.Timedelta(days=1)) and not ((sym[:3] in ("AUD","NZD")) and ((t in CAL["AU"]) or (t in CAL["NZ"]))) for t in m.index]
    return on_bd(m[keep])
def roll(new):
    out=None
    for sym in ["USDJPY","EURJPY","GBPJPY","AUDJPY","CADJPY"]:
        df=load(sym); o=df["open"]; days=pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry=rate_series(sym[:3],days)-rate_series("JPY",days)
        t=o.index[(o.index.dayofweek==2)&(o.index.hour==20)]; cy=carry.reindex(t.normalize()).values; t=t[(cy>=1.0)&~np.isnan(cy)]
        if new: t=pd.DatetimeIndex([x for x in t if not jp_month_end(x)])
        r=trades(sym,t,o.reindex(t).values,-np.ones(len(t)),o.reindex(t+pd.Timedelta(hours=4)).values); r.index=r.index.normalize(); r=on_bd(r)/5
        out=r if out is None else out+r
    return out
def hold(sym): return on_bd(base.hold_cell(sym))
def v4(sym): return on_bd(db.leg_series("v4",sym))
q=open("queue/q52_donchian_vs_hold.py",encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]; qn={"__name__":"q52"}; exec(compile(q,"q52","exec"),qn); brk=on_bd(qn["donchian"]("GER40",120,"trail"))
def logic(key,new):
    if key=="Instant G": return 4*(.537*mon("GBPJPY",new)+.463*mon("AUDJPY",new))+.5*mon("NAS100",new)+.5*mon("US500",new)
    if key=="#14074882 ギャンブル": return 5*(.333*mon("EURJPY",new)+.333*mon("USDJPY",new)+.334*mon("NZDJPY",new))+.5*hold("XAUUSD")
    if key=="EA8": return 3.3*(.260*mon("GBPJPY",new)+.266*mon("EURJPY",new)+.215*mon("AUDJPY",new)+.258*mon("USDJPY",new))+2.0*brk
    if key=="EA3 Mon4 ×2.5": return 2.5*(.260*mon("GBPJPY",new)+.266*mon("EURJPY",new)+.215*mon("AUDJPY",new)+.258*mon("USDJPY",new))
    if key=="パール B案 ×4.0": return 4.0*(.374*mon("GBPJPY",new)+.322*mon("AUDJPY",new)+.304*v4("USDJPY"))
    if key=="EA7g": return 10*(.5*mon("GBPJPY",new)+.5*mon("AUDJPY",new))+20*roll(new)
    if key=="#14166201 v1.31": return on_bd(db.account_composite("FN100k_14166201"))*1.48+3*roll(new)
    if key=="RF5 ×4.8": return 4.8*(.2*on_bd(base.mon_cell("GBPUSD"))+.2*mon("GBPJPY",new)+.2*on_bd(db.leg_series("MonThuS","USDCHF"))+.2*on_bd(db.leg_series("RSI2a","GBPUSD"))+.2*on_bd(db.leg_series("RSI2b","GBPJPY")))
ACC={"Instant G":(19913,20000,22000,18800,.04,None,"trail6"),"#14074882 ギャンブル":(95364,100000,108000,90000,.04,None,None),"EA8":(52191,50000,55000,45000,.04,None,None),
     "EA3 Mon4 ×2.5":(52038,50000,55000,45000,.04,None,None),"パール B案 ×4.0":(5000000,5000000,5400000,4500000,.04,None,None),"EA7g":(19961935,20000000,21200000,19400000,.019,12,"cap3"),
     "#14166201 v1.31":(104218,100000,108000,91000,.04,None,None),"RF5 ×4.8":(100000,100000,110000,90000,.04,None,None)}
rng=np.random.default_rng(5); N=5000; BLOCK=5; DAYS=250
def paths(c,guard,cap=None):
    r=np.clip(np.asarray(c.values,float),-guard,cap); nb=len(r)-BLOCK+1; st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); return r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
def mc(c,bal,init,tgt,floor,guard,dl,mode):
    p=paths(c,guard,0.03 if mode=="cap3" else None); h=DAYS if dl is None else dl; e=bal*np.cumprod(1+p[:,:h],axis=1)
    hwm=np.maximum.accumulate(np.concatenate([np.full((N,1),max(bal,init)),e[:,:-1]],axis=1),axis=1); fl=np.minimum(hwm-init*0.06,init) if mode=="trail6" else np.full_like(e,floor)
    hit=e>=tgt; dq=e<=fl; fh=np.where(hit.any(1),hit.argmax(1),10**6); fd=np.where(dq.any(1),dq.argmax(1),10**6); reach=(fh<fd)&(fh<10**6); fail=(fd<fh)&(fd<10**6)
    return round(reach.mean()*100,1),round(fail.mean()*100,1),(int(np.median(fh[reach])+1) if reach.any() else None)
def st(x):
    eq=(1+x).cumprod(); mo=x.groupby(pd.PeriodIndex(x.index,freq="M")).apply(lambda q:(1+q).prod()-1); yrs=(x.index[-1]-x.index[0]).days/365.25
    return dict(cagr=round(((eq.iloc[-1])**(1/yrs)-1)*100,1),dd=round(float((eq/eq.cummax()-1).min())*100,1),wm=round(float(mo.min())*100,1),wd=round(float(x.min())*100,2),pos=f"{int((mo>0).sum())}/{int((mo!=0).sum())}",sh=round(float(x.mean()/x.std()*np.sqrt(252)),2),n_tr=int((x!=0).sum()))
rows=[]
for key,(bal,init,tgt,floor,guard,dl,mode) in ACC.items():
    o,n=logic(key,False),logic(key,True); so,sn=st(o),st(n); mo,mn=mc(o,bal,init,tgt,floor,guard,dl,mode),mc(n,bal,init,tgt,floor,guard,dl,mode)
    rows.append(dict(account=key,**{f"old_{k}":v for k,v in so.items()},**{f"new_{k}":v for k,v in sn.items()},old_reach=mo[0],old_fail=mo[1],old_med=mo[2],new_reach=mn[0],new_fail=mn[1],new_med=mn[2]))
    print(f"{key:<18} 年率 {so['cagr']:+6.1f}→{sn['cagr']:+6.1f} | DD {so['dd']:6.1f}→{sn['dd']:6.1f} | 最悪月 {so['wm']:5.1f}→{sn['wm']:5.1f} | 最悪日 {so['wd']:5.2f}→{sn['wd']:5.2f} | +月 {so['pos']}→{sn['pos']} | Sharpe {so['sh']:.2f}→{sn['sh']:.2f} | 取引日 {so['n_tr']}→{sn['n_tr']} | 到達/失格/中央 {mo}→{mn}")
pd.DataFrame(rows).to_csv("results/ea_filter_before_after.csv",index=False)
