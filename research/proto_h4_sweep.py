"""
proto_h4_sweep.py — H4化の設計空間を広く掃く(プール合算)。
  問い: D1->H4 で頻度は上がる。では K・RR・保有・「逆張り or 順張り」の
        どこかに優位性(プールPF>1, OOSでも>1)があるか?
  反転フラグ reverse=True は同シグナルで方向を反転(=順張り/モメンタム)。
  手元H1は約2年(2023-08〜2025-08)のみ。最終はユーザー実データで再検証。
"""
import itertools, numpy as np, pandas as pd
import proto_h4 as base

PAIRS = base.PAIRS

def pooled(P, reverse=False):
    allR=[]
    for pair in PAIRS:
        try:
            h1=base.load_h1(pair); h4=base.resample_h4(h1)
            d=backtest(pair,h1,h4,P,reverse)
            if len(d): allR.append(d)
        except Exception as e:
            print("skip",pair,e)
    if not allR: return None
    pool=pd.concat(allR).sort_values("time")
    cut=pool["time"].quantile(0.75)
    full=base.stats(pool,P,"full")
    isg =base.stats(pool[pool["time"]<=cut],P,"is")
    oos =base.stats(pool[pool["time"]>cut],P,"oos")
    return full,isg,oos

def backtest(pair,h1,h4,P,reverse):
    pip=base.pip_size(pair)
    sg=base.compute_signals(h4,P)
    if reverse: sg["signal"]=-sg["signal"]
    spread=pip*P["SpreadMult"]; slip=pip*P["SlipPips"]
    t1=h1.index.values; o1=h1["open"].values; h1h=h1["high"].values
    l1=h1["low"].values; c1=h1["close"].values
    idx=list(sg.index); sigv=sg["signal"].values; atrv=sg["atr"].values
    Rs=[]; times=[]
    for i in range(len(idx)-1):
        s=sigv[i]; atr=atrv[i]
        if s==0 or not (atr==atr) or atr<=0: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        t_next=idx[i+1]
        a=int(np.searchsorted(t1,np.datetime64(t_next),side="left"))
        if a>=len(t1): break
        mid=o1[a]
        if s>0: entry=mid+spread/2+slip; sl=entry-sd; tp=entry+P["RR"]*sd
        else:   entry=mid-spread/2-slip; sl=entry+sd; tp=entry-P["RR"]*sd
        until=t_next+np.timedelta64(P["MaxHoldBars"]*4,"h")
        b=int(np.searchsorted(t1,np.datetime64(until),side="right")); b=max(b,a+1)
        hh=h1h[a:b]; ll=l1[a:b]; R=None
        for k in range(len(hh)):
            if s>0: hit_sl=ll[k]<=sl; hit_tp=hh[k]>=tp
            else:   hit_sl=hh[k]>=sl; hit_tp=ll[k]<=tp
            if hit_sl: R=-1.0; break
            if hit_tp: R=P["RR"]; break
        if R is None:
            last=c1[b-1] if b-1<len(c1) else c1[-1]
            diff=(last-entry) if s>0 else (entry-last)
            R=diff/sd
        Rs.append(R); times.append(pd.Timestamp(t_next))
    return pd.DataFrame({"time":times,"R":Rs})

def main():
    rows=[]
    for reverse in (False, True):
        for K in (2,3,4):
            for RR in (0.8,1.0,1.2,1.5):
                P=dict(base.P); P["K"]=K; P["RR"]=RR
                r=pooled(P,reverse)
                if not r: continue
                full,isg,oos=r
                rows.append(dict(
                    mode=("順張り" if reverse else "逆張り"), K=K, RR=RR,
                    n=full["n"], tr_yr=full["trades_yr"], wr=full["wr"], be=full["be"],
                    PF=full["PF"], totR=full["totR"],
                    OOS_n=oos.get("n",0), OOS_PF=oos.get("PF"), OOS_totR=oos.get("totR")))
    df=pd.DataFrame(rows)
    print("\n===== H4 設計空間スイープ (全ペアプール, 手元H1約2年) =====")
    print(df.to_string(index=False))
    best=df.sort_values("PF",ascending=False).head(5)
    print("\n----- プールPF上位5 -----")
    print(best.to_string(index=False))

if __name__=="__main__":
    main()
