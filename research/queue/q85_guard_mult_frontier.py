# -*- coding: utf-8 -*-
"""docs/322 Q85: 口座規則別のガード・倍率フロンティア(診断・セル 0)。
register_metrics と同じレグ DB(研究系列・Yahoo 日足近似・ロールは Dukascopy H1)で、口座規則ごとに
  倍率 × EA 日次ガード {3,4,5%} × EA 床 {8,9,10%} の格子を 5 日ブロック・ブートストラップ MC(5,000 本・250 営業日)で回す。
採用点 = 年別サブサンプル(2022〜2026)の最悪年でも失格率 ≤ 10% の中で到達率最大(docs/322 の事前指定)。
出力: results/q85_guard_mult_frontier.csv(全格子)・results/q85_guard_mult_selected.json(採用点)。配備は変えない。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
src=open("logic_5y_scorecard.py",encoding="utf-8").read().split("rows = []")[0]
ns={"__name__":"l5","__file__":os.path.join(ROOT,"logic_5y_scorecard.py")}; exec(compile(src,"l5","exec"),ns)
L=ns["L"]; on_bd=ns["on_bd"]; wsum=ns["wsum"]; base=ns["base"]; db=ns["db"]; roll=ns["roll"]; mon4=ns["mon4"]
try:
    q=open("queue/q52_donchian_vs_hold.py",encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
    qn={"__name__":"q52"}; exec(compile(q,"q52","exec"),qn); brk=on_bd(qn["donchian"]("GER40",120,"trail"))
except Exception as e: print("GER40 ブレイク無し:",e); brk=mon4*0
hold_xau=on_bd(db.leg_series("Hold","XAUUSD")); nonfx148=L["非FX ×1.48(FN #14166201)"]
W0,W1=pd.Timestamp("2021-10-01"),pd.Timestamp("2026-08-31")
def win(s): return s[(s.index>=W0)&(s.index<=W1)]
# 口座規則(業者)と「倍率 1 あたりの系列」。倍率は帳簿全体を比例スケール(内部比率は現行 EA のまま)
RULES={
 "FTMO Std 100k(EA10 型: Mon4 + GER40 ブレイク + Hold XAU 0.3)": dict(unit=win((mon4*3.3+brk*2.0+hold_xau*0.3)/3.3), mults=[2.0,2.5,3.3,4.0], target=0.10, firm_floor=0.10, firm_daily=0.05, current=3.3),
 "Fintokei スイング(EA11 型: Mon4 + Roll ×1.0 + 非FX ×0.5)": dict(unit=win((mon4*2.0+roll*1.0+nonfx148*(0.5/1.48))/2.0), mults=[1.5,2.0,2.5,3.3], target=0.08, firm_floor=0.10, firm_daily=0.05, current=2.0),
 "FN 100k(v1.30 型: 非FX + Roll ×3)": dict(unit=win((nonfx148+roll*3)/1.48), mults=[1.0,1.48,2.0,2.5], target=0.08, firm_floor=0.10, firm_daily=0.05, current=1.48),
}
DAILY=[0.03,0.04,0.05]; FLOOR=[0.08,0.09,0.10]
rng=np.random.default_rng(85); N=5000; BLOCK=5; DAYS=250
def mc(s,guard,floor,target,sub=None):
    r=np.asarray(s.values,float); idx=s.index
    if sub is not None:
        m=(idx.year==sub); r=r[m]
    r=np.clip(r,-guard,None); nb=len(r)-BLOCK+1
    if nb<20: return np.nan,np.nan,None
    st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); p=r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
    e=np.cumprod(1+p,axis=1); hit=e>=1+target; dq=e<=1-floor
    fh=np.where(hit.any(axis=1),hit.argmax(axis=1),10**6); fd=np.where(dq.any(axis=1),dq.argmax(axis=1),10**6)
    reach=(fh<fd)&(fh<10**6); fail=(fd<fh)&(fd<10**6)
    med=int(np.median(fh[reach])+1) if reach.any() else None
    return float(reach.mean()),float(fail.mean()),med
rows=[]
for firm,R in RULES.items():
    for m in R["mults"]:
        s=R["unit"]*m
        for g in DAILY:
            for f in FLOOR:
                reach,fail,med=mc(s,g,f,R["target"])
                yr={}
                for y in range(2022,2027):
                    a,b,_=mc(s,g,f,R["target"],sub=y); yr[y]=(a,b)
                worst_fail=max(v[1] for v in yr.values() if not np.isnan(v[1])); worst_year=max(yr,key=lambda y: yr[y][1] if not np.isnan(yr[y][1]) else -1)
                eq=(1+np.clip(s,-g,None)).cumprod(); dd=float((eq/eq.cummax()-1).min()); ann=float(eq.iloc[-1]**(252/len(eq))-1)
                rows.append(dict(firm=firm,mult=m,daily=g,floor=f,reach=round(reach*100,1),fail=round(fail*100,1),median_days=med,worst_year=worst_year,worst_year_fail=round(worst_fail*100,1),
                                 ann=round(ann*100,1),max_dd=round(dd*100,1),**{f"fail_{y}":round(yr[y][1]*100,1) for y in yr},**{f"reach_{y}":round(yr[y][0]*100,1) for y in yr},current=(m==R["current"] and g==0.04)))
                print(f"{firm[:14]} ×{m:<4} 日次{g*100:.0f}% 床{f*100:.0f}% | 到達 {reach*100:5.1f} 失格 {fail*100:5.1f} 中央 {med} | 最悪年 {worst_year} 失格 {worst_fail*100:5.1f} | 年率 {ann*100:6.1f} DD {dd*100:6.1f}",flush=True)
df=pd.DataFrame(rows); df.to_csv("results/q85_guard_mult_frontier.csv",index=False)
sel={}
for firm in RULES:
    d=df[df.firm==firm]; ok=d[d.worst_year_fail<=10.0]
    best=(ok if len(ok) else d).sort_values(["reach","fail"],ascending=[False,True]).iloc[0]
    cur=d[d.current].iloc[0] if d.current.any() else None
    sel[firm]=dict(selected=best.to_dict(),current=(cur.to_dict() if cur is not None else None),n_feasible=int(len(ok)))
    print(f"\n== {firm}: 採用 ×{best.mult} 日次{best.daily*100:.0f}% 床{best.floor*100:.0f}% → 到達 {best.reach} 失格 {best.fail} 最悪年失格 {best.worst_year_fail}({best.worst_year}) | 可行 {len(ok)}/{len(d)}")
    if cur is not None: print(f"   現行 ×{cur.mult} 日次{cur.daily*100:.0f}% 床{cur.floor*100:.0f}% → 到達 {cur.reach} 失格 {cur.fail} 最悪年失格 {cur.worst_year_fail}({cur.worst_year})")
json.dump(sel,open("results/q85_guard_mult_selected.json","w",encoding="utf-8"),ensure_ascii=False,indent=1,default=str)
