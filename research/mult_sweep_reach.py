# -*- coding: utf-8 -*-
"""docs/309: フィルター後のロジックで、口座ごとに倍率を振って到達 / 失格 / 中央日数(現残高起点・250 営業日・EA 日次ガードでクリップ)を求める。"""
import os,sys,numpy as np,pandas as pd,warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,"queue"))
src=open("ea_filter_before_after.py",encoding="utf-8").read().split("rows=[]")[0]
ns={"__name__":"ba","__file__":os.path.join(HERE,"ea_filter_before_after.py")}; exec(compile(src,"ba","exec"),ns)
logic,ACC,mc=ns["logic"],ns["ACC"],ns["mc"]; np_=np
DEP={"Instant G":4.0,"#14074882 ギャンブル":5.0,"EA8":3.3,"EA3 Mon4 ×2.5":2.5,"パール B案 ×4.0":4.0,"EA7g":1.0,"#14166201 v1.31":1.48,"RF5 ×4.8":4.8}
SWEEP={"Instant G":[2,3,4,5,6],"#14074882 ギャンブル":[2,3,4,5,6,7],"EA8":[2,2.5,3.3,4,5],"EA3 Mon4 ×2.5":[2,2.5,3.3,4,5],"パール B案 ×4.0":[2,3,4,5,6],"EA7g":[0.5,0.75,1.0,1.25,1.5],"#14166201 v1.31":[1.0,1.48,2.0,2.5],"RF5 ×4.8":[2,3,4.8,6]}
rows=[]
for key,(bal,init,tgt,floor,guard,dl,mode) in ACC.items():
    unit=logic(key,True)/DEP[key]
    print(f"\n== {key}(配備 {DEP[key]}) ==")
    for m in SWEEP[key]:
        c=unit*m; eq=(1+c).cumprod(); yrs=(c.index[-1]-c.index[0]).days/365.25; cagr=((eq.iloc[-1])**(1/yrs)-1)*100; wd=c.min()*100; dd=(eq/eq.cummax()-1).min()*100
        r,f,med=mc(c,bal,init,tgt,floor,guard,dl,mode); ev=r-f
        rows.append(dict(account=key,mult=m,cagr=round(cagr,1),worst_day=round(wd,2),max_dd=round(dd,1),reach=r,fail=f,median_days=med))
        print(f"  ×{m:<5} 年率 {cagr:6.1f}% 最悪日 {wd:6.2f}% DD {dd:6.1f}% | 到達 {r:5.1f}% 失格 {f:5.1f}% 中央 {med} 日 | 到達−失格 {ev:5.1f}{'  ← 配備' if m==DEP[key] else ''}")
pd.DataFrame(rows).to_csv("results/mult_sweep_reach.csv",index=False)
