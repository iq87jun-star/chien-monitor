# -*- coding: utf-8 -*-
"""docs/313 §4: Mon4 の災害 SL(なし / 2.5×ATR / 3.0×ATR)で到達・失格・中央日数がどう変わるか(EA3 口座条件・×2.5 と ×3.3)。
系列は queue/q76_mon_stoploss.py の shots_sl(祝日フィルター無し・4 ショット 24h)。MC は ea_filter_before_after.py と同じ(5000 本・ブロック 5 日・250 日)。"""
import os,sys,re,numpy as np,pandas as pd,warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,"queue"))
src=open("ea_filter_before_after.py",encoding="utf-8").read().split("rows=[]")[0]
ns={"__name__":"ba","__file__":os.path.join(HERE,"ea_filter_before_after.py")}; exec(compile(src,"ba","exec"),ns); ACC,mc,st=ns["ACC"],ns["mc"],ns["st"]
q=open("queue/q76_mon_stoploss.py",encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
qn={"__name__":"q76","__file__":os.path.join(HERE,"queue","q76_mon_stoploss.py")}; sys.argv=["x","0"]; exec(compile(q,"q76","exec"),qn); shots_sl,W=qn["shots_sl"],qn["W"]
def series(k):
    out=None
    for p,wt in W["Mon4"].items():
        s,_,_=shots_sl(p,k); x=s*wt; out=x if out is None else out.add(x,fill_value=0)
    out=out[(out.index>=qn['IS0'])&(out.index<=qn['END'])]; bd=pd.bdate_range(out.index.min(),out.index.max()); return out.reindex(bd).fillna(0.0)  # 5 年窓(2021-10〜)
bal,init,tgt,floor,guard,dl,mode=ACC["EA3 Mon4 ×2.5"]; rows=[]
for k in (None,2.5,3.0,3.5):
    u=series(k)
    for m in (2.5,3.3,4.0):
        c=u*m; s=st(c); r,f,med=mc(c,bal,init,tgt,floor,guard,dl,mode)
        rows.append(dict(sl=("なし" if k is None else f"{k}×ATR"),mult=m,**s,reach=r,fail=f,median_days=med))
        print(f"SL {('なし' if k is None else str(k)+'×ATR'):8s} ×{m:<4} 年率 {s['cagr']:6.1f}% DD {s['dd']:6.1f}% 最悪月 {s['wm']:5.1f}% 最悪日 {s['wd']:5.2f}% Sharpe {s['sh']:.2f} | 到達 {r:5.1f}% 失格 {f:5.1f}% 中央 {med} 日")
pd.DataFrame(rows).to_csv("results/sl_reach_mc.csv",index=False)
