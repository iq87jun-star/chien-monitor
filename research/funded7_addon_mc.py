# -*- coding: utf-8 -*-
"""docs/242: Funded7 の損失拡大アドオン(総損失 +5% / 日次 +5%)が校正倍率・資金化率・資金化後生存に効くかを MC で比較。research/ で実行。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import recentfit_screen as base, deployed_book as db, plusmonth_search_h1 as H
from forward.paper_forward import refresh_live
from plusmonth_portfolio import perf
from sess_top5_portfolio import daily
import ea4_compare as E
refresh_live(); rng=np.random.default_rng(7)
WA2={("Mon","GBPJPY"):.260,("Mon","EURJPY"):.266,("Mon","AUDJPY"):.215,("Mon","USDJPY"):.258}
SA={k:db.leg_series(*k) for k in WA2}; cA=E.comp(SA,WA2)
H.A=pd.Timestamp("2021-09-25"); SB={k:daily(sym,h0,span,3) for k,sym,h0,span in E.S8}
cB5=E.comp(SB,E.invvol(SB,[k for k,*_ in E.S5])); cB8=E.comp(SB,E.invvol(SB,[k for k,*_ in E.S8]))
idx=cA.index.union(cB8.index); a,b5,b8=(x.reindex(idx).fillna(0) for x in (cA,cB5,cB8))
eas={"EA3' Mon4":a,"EA2' Mon4+Sess5":0.5*a+0.5*b5,"EA4 Sess8":b8}
rules={"標準 10/5":(0.10,0.04,0.08),"アドオン 15/10":(0.15,0.08,0.12)}
def survive(c,mult,dd,n=5000,days=250,block=5):
    r=np.asarray(c.values,float)*mult; nb=len(r)-block+1
    st=rng.integers(0,nb,size=(n,days//block+1)); p=r[(st[:,:,None]+np.arange(block)[None,None,:])].reshape(n,-1)[:,:days]
    eq=np.cumprod(1+p,axis=1); return round(float((eq.min(axis=1)<=1-dd).mean())*100,1), round(float(np.median(eq[:,-1])-1)*100,1)
base.P2_TARGET=0.05
out={}
for nm,c in eas.items():
    c12=c[c.index>=E.END-pd.DateOffset(months=12)]
    for rn,(dd,guard,floor) in rules.items():
        base.MAX_DD=dd; base.DAY_GUARD=guard
        raw=min(base.calibrate(c,guard,floor), base.calibrate(c12,guard,floor)); mult=min(raw,6.0)
        for tag,m in (("校正",mult),):
            p=perf(c,m); mc=base.mc_challenge(c12,m,rng); sv=survive(c12,m,dd)
            out[(nm,rn,tag)]=dict(raw=raw,mult=m,cagr=round(((1+p["total_pct"]/100)**(1/4.25)-1)*100,1),dd=p["max_dd_pct"],wd=p["worst_day_pct"],funded=mc["funded"],fail=mc["fail"],days=mc["funded_days_med"],p90=mc["funded_days_p90"],fail250=sv[0],med250=sv[1])
        # also: same multiplier as standard but wider rule (pure safety)
    base.MAX_DD=0.15; base.DAY_GUARD=0.08
    m0=out[(nm,"標準 10/5","校正")]["mult"]; mc=base.mc_challenge(c12,m0,rng); sv=survive(c12,m0,0.15)
    out[(nm,"アドオン 15/10","標準倍率のまま")]=dict(raw=m0,mult=m0,cagr=out[(nm,"標準 10/5","校正")]["cagr"],dd=out[(nm,"標準 10/5","校正")]["dd"],wd=out[(nm,"標準 10/5","校正")]["wd"],funded=mc["funded"],fail=mc["fail"],days=mc["funded_days_med"],p90=mc["funded_days_p90"],fail250=sv[0],med250=sv[1])
df=pd.DataFrame(out).T; print(df.to_string())
print("\n--- EA3' Mon4: アドオン単体 ---")
c=eas["EA3' Mon4"]; c12=c[c.index>=E.END-pd.DateOffset(months=12)]
for rn,(dd,guard,floor) in {"総損失のみ 15/5":(0.15,0.04,0.12),"日次のみ 10/10":(0.10,0.08,0.08),"両方 15/10":(0.15,0.08,0.12)}.items():
    base.MAX_DD=dd; base.DAY_GUARD=guard
    raw=min(base.calibrate(c,guard,floor), base.calibrate(c12,guard,floor)); m=min(raw,6.0)
    p=perf(c,m); mc=base.mc_challenge(c12,m,rng); sv=survive(c12,m,dd)
    print(f"{rn:14s} ×{m:4.2f} 年率 {((1+p['total_pct']/100)**(1/4.25)-1)*100:5.1f}% DD {p['max_dd_pct']:6.2f} 最悪日 {p['worst_day_pct']:6.2f} | 資金化 {mc['funded']}% 失格 {mc['fail']}% 中央 {mc['funded_days_med']}日 | 資金化後250日 失格 {sv[0]}%")
