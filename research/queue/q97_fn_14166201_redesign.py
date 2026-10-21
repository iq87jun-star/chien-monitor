# -*- coding: utf-8 -*-
"""docs/322 Q97: FN 100k #14166201 の構成見直し(診断・セル 0)。
Q85(docs/325)で現行(非FX + Roll ×3)は全格子で最悪年失格 > 10%。FN 内の同一取引禁止(docs/292・298)で
Instant G(Mon GBPJPY/AUDJPY・Mon NAS100/US500)・#14074882(Mon EURJPY/USDJPY/NZDJPY・Hold XAU)と重ならない
Mon 銘柄 = CADJPY / CHFJPY(docs/290 の Mon 族・Sharpe 0.87 / 1.06)と指数 Mon GER40 を核にした候補を、
Q85 と同じ MC(5 日ブロック・5,000 本・250 営業日・年別サブサンプル)と同じ FN Stellar 規則(目標 8%・床 10%・日次 5%)で比較する。
採用規則(Q85 と同じ事前指定): 最悪年でも失格率 ≤ 10% の中で到達率最大。配備は変えない(EA は版 +0.01・「切替」後)。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
src=open("logic_5y_scorecard.py",encoding="utf-8").read().split("rows = []")[0]
ns={"__name__":"l5","__file__":os.path.join(ROOT,"logic_5y_scorecard.py")}; exec(compile(src,"l5","exec"),ns)
L=ns["L"]; on_bd=ns["on_bd"]; wsum=ns["wsum"]; base=ns["base"]; db=ns["db"]; roll=ns["roll"]
W0,W1=pd.Timestamp("2021-10-01"),pd.Timestamp("2026-08-31")
def win(s): return s[(s.index>=W0)&(s.index<=W1)]
cell=lambda f,s: on_bd(db.leg_series(f,s))
mon2=wsum([(cell("Mon","CADJPY"),.5),(cell("Mon","CHFJPY"),.5)])
hold_uw=wsum([(cell("Hold","UK100"),.491/.644),(cell("Hold","WTI"),.153/.644)])   # 現行の UK100:WTI 比(0.491:0.153)を合計 1 に正規化
ger=cell("Mon","GER40"); nonfx148=L["非FX ×1.48(FN #14166201)"]
# 候補: unit = 倍率 ×1 あたりの系列。倍率は帳簿全体を比例スケール
CANDS={
 "C0 現行 v1.32(非FX UK100/WTI/BTC/ETH + Roll ×3)": dict(unit=win((nonfx148+roll*3)/1.48), mults=[1.0,1.48,2.0], current=1.48),
 "C1 BTC/ETH 外し(Hold UK100/WTI ×1 + Roll ×2.03)": dict(unit=win(hold_uw*0.644+roll*(3/1.48)), mults=[1.48,2.22,3.0]),
 "C2 Mon2 CADJPY/CHFJPY のみ": dict(unit=win(mon2), mults=[2.0,3.0,4.0,5.0,6.0]),
 "C3 Mon2 + Roll ×1(EA7 型)": dict(unit=win(mon2+roll*1.0), mults=[2.0,3.0,4.0,5.0]),
 "C4 Mon2 + Roll ×1 + Hold UK100/WTI ×0.5(EA11 型)": dict(unit=win(mon2+roll*1.0+hold_uw*0.5), mults=[2.0,3.0,4.0,5.0]),
 "C5 Mon2 + Mon GER40 ×0.5": dict(unit=win(mon2+ger*0.5), mults=[2.0,3.0,4.0,5.0]),
 "C6 Mon2 + Mon GER40 ×0.5 + Roll ×1": dict(unit=win(mon2+ger*0.5+roll*1.0), mults=[2.0,3.0,4.0,5.0]),
}
TARGET,FIRM_FLOOR=0.08,0.10; DAILY=[0.03,0.04,0.05]; FLOOR=[0.09,0.10]
rng=np.random.default_rng(97); N=5000; BLOCK=5; DAYS=250
def mc(s,guard,floor,target,sub=None):
    r=np.asarray(s.values,float); idx=s.index
    if sub is not None: r=r[idx.year==sub]
    r=np.clip(r,-guard,None); nb=len(r)-BLOCK+1
    if nb<20: return np.nan,np.nan,None
    st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); p=r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
    e=np.cumprod(1+p,axis=1); hit=e>=1+target; dq=e<=1-floor
    fh=np.where(hit.any(axis=1),hit.argmax(axis=1),10**6); fd=np.where(dq.any(axis=1),dq.argmax(axis=1),10**6)
    reach=(fh<fd)&(fh<10**6); fail=(fd<fh)&(fd<10**6)
    med=int(np.median(fh[reach])+1) if reach.any() else None
    return float(reach.mean()),float(fail.mean()),med
rows=[]
for cand,R in CANDS.items():
    for m in R["mults"]:
        s=R["unit"]*m
        for g in DAILY:
            for f in FLOOR:
                reach,fail,med=mc(s,g,f,TARGET); yr={y:mc(s,g,f,TARGET,sub=y)[:2] for y in range(2022,2027)}
                ok={y:v for y,v in yr.items() if not np.isnan(v[1])}; wy=max(ok,key=lambda y: ok[y][1]); wf=ok[wy][1]
                eq=(1+np.clip(s,-g,None)).cumprod(); dd=float((eq/eq.cummax()-1).min()); ann=float(eq.iloc[-1]**(252/len(eq))-1)
                sh=float(s.mean()/s.std()*np.sqrt(252)) if s.std()>0 else 0.0
                rows.append(dict(cand=cand,mult=m,daily=g,floor=f,reach=round(reach*100,1),fail=round(fail*100,1),median_days=med,worst_year=wy,worst_year_fail=round(wf*100,1),
                                 ann=round(ann*100,1),max_dd=round(dd*100,1),sharpe=round(sh,2),**{f"fail_{y}":round(yr[y][1]*100,1) for y in yr},**{f"reach_{y}":round(yr[y][0]*100,1) for y in yr},
                                 current=(m==R.get("current") and g==0.04 and f==0.10)))
                print(f"{cand[:28]:<28} ×{m:<4} 日次{g*100:.0f}% 床{f*100:.0f}% | 到達 {reach*100:5.1f} 失格 {fail*100:5.1f} 中央 {med} | 最悪年 {wy} {wf*100:5.1f} | 年率 {ann*100:6.1f} DD {dd*100:6.1f} Sh {sh:4.2f}",flush=True)
df=pd.DataFrame(rows); df.to_csv("results/q97_fn_14166201_redesign.csv",index=False)
print("\n== 候補別の採用点(床 10%・最悪年失格 ≤ 10% の中で到達率最大) ==")
sel={}
for cand in CANDS:
    d=df[(df.cand==cand)&(df.floor==0.10)]; ok=d[d.worst_year_fail<=10.0]
    best=(ok if len(ok) else d).sort_values(["reach","fail"],ascending=[False,True]).iloc[0]
    sel[cand]=dict(selected=best.to_dict(),n_feasible=int(len(ok)),feasible=bool(len(ok)))
    print(f"{cand}: {'可行' if len(ok) else '不可行(最良)'} ×{best.mult} 日次{best.daily*100:.0f}% → 到達 {best.reach} 失格 {best.fail} 中央 {best.median_days} 日 最悪年 {best.worst_year} {best.worst_year_fail} 年率 {best.ann} DD {best.max_dd} Sh {best.sharpe}")
json.dump(sel,open("results/q97_fn_14166201_selected.json","w",encoding="utf-8"),ensure_ascii=False,indent=1,default=str)
