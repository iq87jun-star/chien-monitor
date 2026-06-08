# -*- coding: utf-8 -*-
"""
prop_unified_timeprojection.py — 「楽観(WR仮定) vs 実績」を1つの土俵に統一した到達月推計。

経緯: docs/46「中央3ヶ月」はトレード単位・WR50%/RR1.8仮定(montecarlo_2phase)の楽観値。
      直近の「中央11ヶ月」は実績月次ブロックBSの保守値。本書は両者を同一エンジンに載せ、
      4戦略の【実績・週次リターン分布】で2フェーズ・チャレンジを駆動して統一比較する。

実績週次系列:
  v7   = 円3クロス(EURJPY/GBPJPY/USDJPY) 月曜LONG o2o 等加重(実コスト後) 週次
  v4   = 9ペア日足k≥4合議(SL1.5ATR/RR1.2/8日) のRをエントリー週で集計→口座比(/トレードリスク基準で正規化)
  E5   = 多資産(金+指数)月次TSMOM を週へ均等配分(小ウェイト=近似)
  E-Mon= 株価指数3(US500/NAS100/GER40) 月曜LONG o2o 等加重 週次
合成: S0=3種(40:40:20) / S1=4種(25:35:15:25)。各成分を週次ボラ正規化→重み付け。
倍率: 1.0x=「3種の10年maxDDが-6%」係数。x2/x3を評価。

チャレンジ(2フェーズ・週次ブロックBS, block=4週):
  P1 +8% / P2 +5% / 各フェーズ初期比 -10%で失格 / 無制限(上限156週)。
出力: 中央到達(月) / 3ヶ月(13週)・6ヶ月(26週)・12ヶ月(52週)以内 資金化率 / 最終資金化率 / 失格率。
参考: 楽観(WR50% montecarlo_2phase: AvgDays56≒2.7ヶ月)を併記。
注意: シミュレーション・配当抜き指数・日次-4%未モデル。実値はデモで。数字は盛らない。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_backtester as rb, ensemble_meanrev as em
import p2_portfolio_validate as V
import p2_edge_search as P

HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,"data")
SEED=20260608; N=20000; BLOCK=4; CAPW=156

def jpy_monday_weekly():
    parts=[]
    for p in ["EURJPY","GBPJPY","USDJPY"]:
        df=pd.read_csv(os.path.join(DATA,f"{p}_d.csv"))
        df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce")
        df=df.dropna(subset=["t"]).sort_values("t")
        df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
        df=df.groupby("trade_date").last(); df["weekday"]=df.index.dayofweek
        df=df[df["weekday"]<=4]; df["o2o"]=df["open"].shift(-1)/df["open"]-1.0
        sub=df[df["weekday"]==0].dropna(subset=["o2o"])
        pip=0.01; r=(sub["o2o"]-(2.0+1.0)*pip/sub["open"]); r.index=r.index.to_period("W")
        parts.append(r.groupby(r.index).mean())
    return pd.concat(parts,axis=1).mean(axis=1).dropna()

def v4_weekly():
    from collections import defaultdict
    wk=defaultdict(float)
    PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
    for p in PAIRS:
        ts,o,h,l,c=rb.load_daily(p); sig=em.signals_confluence(o,h,l,c,k_required=4)
        pip=rb.pip_size(p); atr=rb.atr_wilder(h,l,c,14)
        half=(rb.SPREAD_PIPS.get(p,rb.DEFAULT_SPREAD)/2.0+rb.SLIPPAGE_PIPS)*pip; pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn=pos["dir"];e=pos["entry"];slv=pos["sl"];tp=pos["tp"];hi=h[i];lo=l[i];ex=None
                if dirn>0:
                    if lo-half<=slv: ex=slv
                    elif hi-half>=tp: ex=tp
                else:
                    if hi+half>=slv: ex=slv
                    elif lo+half<=tp: ex=tp
                if ex is None and (i-pos["i"])>=8: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    r=((ex-e) if dirn>0 else (e-ex))/pos["risk"]
                    wkkey=pd.Timestamp(str(ts[pos["i"]])[:10]).to_period("W")
                    wk[wkkey]+=r*0.004   # 1トレード=口座0.4%リスク基準でR→口座比に換算
                    pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    e=o[i]+(half if s>0 else -half); risk=atr[i-1]*1.5
                    slv=e-risk if s>0 else e+risk; tp=e+1.2*risk if s>0 else e-1.2*risk
                    pos={"dir":s,"entry":e,"sl":slv,"tp":tp,"risk":risk,"i":i}
    s=pd.Series(wk).sort_index(); return s

def e5_weekly():
    e5m=P.p1_e5_monthly()                       # 月次(Period[M])
    # 月次→週次へ均等配分(各月の週数で割る)
    rows={}
    for per,val in e5m.items():
        start=per.to_timestamp(how="start"); end=per.to_timestamp(how="end")
        weeks=pd.period_range(start=start,end=end,freq="W")
        for w in weeks: rows[w]=rows.get(w,0.0)+val/len(weeks)
    return pd.Series(rows).sort_index()

def emon_weekly():
    return V.basket_weekly(["US500","NAS100","GER40"])

def znorm(s): s=s.dropna(); return s/s.std()*0.005 if s.std()>0 else s  # 週次ボラ0.5%に正規化(複利安定・k1で再スケール)

def build():
    v7=jpy_monday_weekly(); v4=v4_weekly(); e5=e5_weekly(); emon=emon_weekly()
    df=pd.concat([znorm(v7).rename("v7"),znorm(v4).rename("v4"),
                  znorm(e5).rename("E5"),znorm(emon).rename("E-Mon")],axis=1).fillna(0.0)
    # 共通期間(全系列が動く範囲)
    df=df.loc[df.index>=max(v7.index.min(),v4.index.min(),emon.index.min())]
    return df

def mdd(a): s=pd.Series(a); eq=(1+s).cumprod(); return float(((eq-eq.cummax())/eq.cummax()).min())

def boot(arr,rng,n):
    out=[]; m=len(arr)
    while len(out)<n:
        st=rng.integers(0,max(1,m-BLOCK)); out.extend(arr[st:st+BLOCK])
    return out[:n]
def phase(arr,rng,tgt):
    eq=1.0; w=0
    for r in boot(arr,rng,CAPW):
        eq*=(1+r); w+=1
        if eq-1<=-0.10: return("DQ",w)
        if eq-1>=tgt: return("PASS",w)
    return("TO",w)
def challenge(arr,rng):
    a=phase(arr,rng,0.08)
    if a[0]!="PASS": return (a[0],a[1])
    b=phase(arr,rng,0.05)
    return ("FUNDED" if b[0]=="PASS" else b[0], a[1]+b[1])

def evaluate(arr):
    rng=np.random.default_rng(SEED)
    res=[challenge(arr,rng) for _ in range(N)]
    fw=[w for (o,w) in res if o=="FUNDED"]; dq=sum(1 for (o,_) in res if o=="DQ")
    fw=np.array(fw)
    def within(wk): return round(100*np.mean([1 for w in fw if w<=wk])/1 if False else 100*np.mean(fw<=wk),1) if len(fw) else 0
    return dict(med_mo=round(float(np.median(fw))/4.345,1) if len(fw) else None,
                mean_mo=round(float(np.mean(fw))/4.345,1) if len(fw) else None,
                within3mo=round(100*np.mean(fw<=13),1) if len(fw) else 0,
                within6mo=round(100*np.mean(fw<=26),1) if len(fw) else 0,
                within12mo=round(100*np.mean(fw<=52),1) if len(fw) else 0,
                funded_pct=round(100*len(fw)/N,1), dq_pct=round(100*dq/N,1))

def main():
    df=build()
    print(f"共通週数={len(df)}  期間 {df.index.min()}..{df.index.max()}")
    S0={"v7":.40,"v4":.40,"E5":.20,"E-Mon":0.0}
    S1={"v7":.25,"v4":.35,"E5":.15,"E-Mon":.25}
    def blend(w): return sum(df[k]*v for k,v in w.items() if v).values
    b0=blend(S0); b1=blend(S1)
    k1=0.06/abs(mdd(b0))   # 1.0x=3種10年maxDD-6%
    out={"weeks":len(df),"optimistic_ref":"WR50%/RR1.8 trade-level (montecarlo_2phase) AvgDays56≒2.7ヶ月"}
    print(f"\n参考(楽観・docs/46): WR50%/RR1.8 トレード単位 → 中央≒2.7ヶ月\n")
    print("=== 実績・週次分布で駆動した統一結果 ===")
    print(f"{'構成/倍率':16s} 中央(月) 平均  3ヶ月内 6ヶ月内 12ヶ月内 最終資金化 失格  10yrmaxDD")
    for mult in (2.0,3.0):
        for nm,b in (("3種",b0),("4種",b1)):
            a=b*k1*mult; r=evaluate(a)
            out[f"{nm}_x{int(mult)}"]=dict(**r, maxDD=round(mdd(a)*100,1))
            print(f"{nm} x{int(mult):<11} {str(r['med_mo']):>6}  {str(r['mean_mo']):>4}  "
                  f"{r['within3mo']:5}% {r['within6mo']:5}% {r['within12mo']:6}%  {r['funded_pct']:6}%  {r['dq_pct']:4}%  {mdd(a*1.0)*100:5.1f}%")
    with open(os.path.join(HERE,"results","prop_unified_timeprojection.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("\n保存: research/results/prop_unified_timeprojection.json")

if __name__=="__main__":
    main()
