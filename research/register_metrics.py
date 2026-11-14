# -*- coding: utf-8 -*-
"""稼働 EA 台帳(アーティファクト)用の指標: 口座ごとの採用ロジックの 5 年月次リターン(配備倍率)と、現残高からの目標到達 MC(中央値日数 → 予定月)。
出力 results/register_metrics.json。研究系列(Yahoo 日足近似・ロールは Dukascopy H1 3pip)・日次ガードは EA 値でクリップ・実口座成績ではない。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0,HERE)
src=open("logic_5y_scorecard.py",encoding="utf-8").read().split("rows = []")[0]
ns={"__name__":"l5","__file__":os.path.join(HERE,"logic_5y_scorecard.py")}; exec(compile(src,"l5","exec"),ns)
L=ns["L"]; on_bd=ns["on_bd"]; wsum=ns["wsum"]; base=ns["base"]; db=ns["db"]; roll=ns["roll"]; mon4=ns["mon4"]
def cell(f,s): return db.leg_series(f,s)
# 追加ロジック(9/25〜26 の変更分)
L["Instant G"]=on_bd(wsum([(cell("Mon","GBPJPY"),.537*4),(cell("Mon","AUDJPY"),.463*4),(cell("Mon","NAS100"),.5),(cell("Mon","US500"),.5)]))
L["#14074882 ギャンブル"]=on_bd(wsum([(cell("Mon","EURJPY"),.333*5),(cell("Mon","USDJPY"),.333*5),(cell("Mon","NZDJPY"),.334*5),(cell("Hold","XAUUSD"),.5)]))
L["#14166201 v1.30"]=L["非FX ×1.48(FN #14166201)"]+roll*3
try:
    sys.path.insert(0,os.path.join(HERE,"queue")); q=open("queue/q52_donchian_vs_hold.py",encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
    qn={"__name__":"q52"}; exec(compile(q,"q52","exec"),qn); r=qn["donchian"]("GER40",120,"trail"); brk=on_bd(r)
    L["EA8"]=mon4*3.3+brk*2.0
except Exception as e: print("EA8 breakout 無し:",e); L["EA8"]=mon4*3.3
L["1-Step A ×1.5"]=on_bd(wsum([(cell("Hold","XAUUSD"),.12),(cell("Mon","GBPJPY"),.632),(cell("Mon","NAS100"),.248)]))*1.5
ACC=[ # key, logic, 残高, 初期, 目標, 床(静的), EA日次ガード, 期限(営業日, None=無期限), 備考
 ("FN Instant 20k #11988011","Instant G",19913,20000,22000,18800,0.04,None,"目標なし。参考値 +10%(22,000・スケールアップ線)。床 = HWM−6%(初期固定)"),
 ("FN 100k #14074882","#14074882 ギャンブル",95364,100000,108000,90000,0.04,None,"P1 +8%・失格 90,000・日次 5%(EA 4%)"),
 ("FN 100k #14166201","#14166201 v1.30",104218,100000,108000,91000,0.04,None,"P1 +8%・EA 床 91,000・日次 5%(EA 4%)"),
 ("FTMO 50k #521100397","EA8",52191,50000,55000,45000,0.04,None,"9/30 から EA8。P1 +10%・失格 45,000・日次 5%(EA 4%)"),
 ("FTMO 50k #531407058","Mon4 ×2.5(EA3・FTMO50k #531407058)",52038,50000,55000,45000,0.04,None,"EA3 単独(C6m は 9/30 期限)。P1 +10%"),
 ("FTMO 100k #531343523","RF5 A案 5スリーブ ×4.8(FTMO100k #531343523)",100000,100000,110000,90000,0.04,None,"⚠残高未取得 → 初期 100,000 と仮定。P1 +10%"),
 ("FTMO 100k 1-Step #531466484","1-Step A ×1.5",100000,100000,110000,90000,0.024,None,"未稼働。装着した場合(A ×1.5)。床は EOD トレーリング 10%"),
 ("Fintokei パール 500万","B案 RecentFit ×4.0(Fintokei パール)",5000000,5000000,5400000,4500000,0.04,None,"⚠残高未取得 → 初期 500 万と仮定。P1 +8%・失格 10%・日次 5%(EA 4%)と仮定"),
 ("Fintokei 速攻プロ #6078225","EA7g Mon2 ×10 + ロール ×20(速攻プロ ギャンブル)",19961935,20000000,21200000,19400000,0.019,12,"目標 +6%・失格 −3%・日次 −2%(EA 1.9%)・期限 10/13(営業日 12)。+3%/日の利益上限は日次クリップで近似(翌日読取専用は未モデル化)"),
]
rng=np.random.default_rng(5); N=5000; BLOCK=5; DAYS=250
def paths(c,guard,cap=None):
    r=np.clip(np.asarray(c.values,float),-guard,cap); nb=len(r)-BLOCK+1
    st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); return r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
START=pd.Timestamp("2026-09-28")
out={"asof":"2026-09-26","start":str(START.date()),"accounts":[]}
for key,logic,bal,init,tgt,floor,guard,dl,note in ACC:
    s=L[logic]; s=s[(s.index>=pd.Timestamp("2021-10-01"))&(s.index<=pd.Timestamp("2026-08-31"))]
    mon=s.groupby(pd.PeriodIndex(s.index,freq="M")).apply(lambda q:(1+q).prod()-1)
    grid={str(y):{str(m):(round(float(mon[pd.Period(f"{y}-{m:02d}")])*100,2) if pd.Period(f"{y}-{m:02d}") in mon.index else None) for m in range(1,13)} for y in range(2021,2027)}
    yr={str(y):round(float((1+s[s.index.year==y]).prod()-1)*100,1) for y in range(2021,2027)}
    eq=(1+s).cumprod(); cum=round(float(eq.iloc[-1]-1)*100,1); dd=round(float((eq/eq.cummax()-1).min())*100,1); pos=f"{int((mon>0).sum())}/{int((mon!=0).sum())}"
    p=paths(s,guard,0.03 if "速攻" in key else None); horizon=DAYS if dl is None else dl
    e=bal*np.cumprod(1+p[:,:horizon],axis=1); hwm=np.maximum.accumulate(np.concatenate([np.full((N,1),max(bal,init)),e[:,:-1]],axis=1),axis=1)
    fl=np.full_like(e,floor) if "1-Step" not in key and "Instant" not in key else np.minimum(hwm-init*0.06 if "Instant" in key else hwm-init*0.10, init)
    hit=(e>=tgt); dq=(e<=fl)
    first_hit=np.where(hit.any(axis=1),hit.argmax(axis=1),10**6); first_dq=np.where(dq.any(axis=1),dq.argmax(axis=1),10**6)
    reach=(first_hit<first_dq)&(first_hit<10**6); fail=(first_dq<first_hit)&(first_dq<10**6)
    days=first_hit[reach]+1; med=int(np.median(days)) if reach.any() else None; p75=int(np.percentile(days,75)) if reach.any() else None
    med_date=str((START+pd.offsets.BDay(med)).date()) if med else None; p75_date=str((START+pd.offsets.BDay(p75)).date()) if p75 else None
    out["accounts"].append(dict(account=key,logic=logic,balance=bal,initial=init,target=tgt,floor=floor,guard=guard,deadline_bdays=dl,note=note,
        cum5y=cum,max_dd=dd,pos_months=pos,by_year=yr,monthly=grid,
        mc=dict(reach=round(float(reach.mean())*100,1),fail=round(float(fail.mean())*100,1),neither=round(float((~reach&~fail).mean())*100,1),median_days=med,median_date=med_date,p75_days=p75,p75_date=p75_date)))
    print(f"{key:<32} 5y {cum:+7.1f}% DD {dd:6.1f} +月 {pos:>6} | 到達 {reach.mean()*100:5.1f}% 失格 {fail.mean()*100:5.1f}% 中央 {med} 日 → {med_date} (p75 {p75_date})")
json.dump(out,open("results/register_metrics.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
