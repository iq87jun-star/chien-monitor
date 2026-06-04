# -*- coding: utf-8 -*-
"""
ensemble_meanrev.py — 多信号アンサンブル(合議フィルタ)の検定。
単体テクニカルが全滅したため、質的に異なる「合議(confluence)」を試す:
  複数の独立した『売られすぎ/買われすぎ』シグナルが同時に一致したときだけ建てる。
  仮説: ノイズ的な単発逆張りより、複数条件の一致は精度(勝率)が上がりうる。
評価: 日足10年・全ペア・IS(前60%)で一切調整せず、OOS(後40%)で素の成績。
      プール/ペア別/前後半レジーム、ブートストラップP(PF<=1)。
正直: これも効かない可能性が高い。結果をそのまま報告する。
"""
import os, csv, math, json
import numpy as np
import research_backtester as rb

PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]

def bb_z(c, n=20):
    """ボリンジャー的 zスコア = (close - SMA)/STD。"""
    z=np.full_like(c, np.nan)
    for i in range(n, len(c)):
        w=c[i-n:i]; m=w.mean(); s=w.std(ddof=1)
        if s>0: z[i]=(c[i]-m)/s
    return z

def signals_confluence(o,h,l,c, k_required=3):
    """4つの弱い逆張り条件の合議。k_required個以上一致でエントリー。"""
    rsi=rb.rsi_wilder(c,14)
    z=bb_z(c,20)
    # 連続下落/上昇日数
    down=np.zeros(len(c)); up=np.zeros(len(c))
    for i in range(1,len(c)):
        down[i]=down[i-1]+1 if c[i]<c[i-1] else 0
        up[i]=up[i-1]+1 if c[i]>c[i-1] else 0
    # 当日リターンの大きさ(行き過ぎ)
    ret=np.zeros(len(c)); ret[1:]=(c[1:]-c[:-1])/c[:-1]
    sig=np.zeros(len(c))
    for i in range(20,len(c)):
        zlo = (not np.isnan(z[i])) and (z[i]<-1.5)
        zhi = (not np.isnan(z[i])) and (z[i]>1.5)
        # 買い条件(売られすぎ): int()で明示的に票を数える
        buy_votes  = int(rsi[i]<35) + int(zlo) + int(down[i]>=3) + int(ret[i]<-0.005)
        sell_votes = int(rsi[i]>65) + int(zhi) + int(up[i]>=3)   + int(ret[i]>0.005)
        if buy_votes>=k_required and buy_votes>sell_votes: sig[i]=1
        elif sell_votes>=k_required and sell_votes>buy_votes: sig[i]=-1
    return sig

def evalseg(pair,sig,o,h,l,c,a,b,sl_atr=1.5,rr=1.2,max_hold=8):
    i,j=int(len(c)*a),int(len(c)*b)
    return rb.simulate(pair,o[i:j],h[i:j],l[i:j],c[i:j],sig[i:j],
                       sl_atr=sl_atr,rr=rr,max_hold=max_hold)

def run(k_required):
    print(f"\n================= 合議 k>={k_required} (4条件中) =================")
    print(f"{'pair':<8}{'ISn':>5}{'IS_PF':>7}{'OOSn':>6}{'OOS_PF':>8}{'exp':>8}{'WR':>7}{'P':>8}{'前半':>7}{'後半':>7}")
    pool_oos=[]; perpair_gt1=0; npairs=0
    for p in PAIRS:
        ts,o,h,l,c=rb.load_daily(p)
        sig=signals_confluence(o,h,l,c,k_required)
        Ris=evalseg(p,sig,o,h,l,c,0,0.6)
        Roos=evalseg(p,sig,o,h,l,c,0.6,1.0)
        Rh1=evalseg(p,sig,o,h,l,c,0.6,0.8)
        Rh2=evalseg(p,sig,o,h,l,c,0.8,1.0)
        pool_oos.append(Roos)
        sis=rb.stats(Ris); soos=rb.stats(Roos); s1=rb.stats(Rh1); s2=rb.stats(Rh2)
        if soos.get("n",0)>=10:
            npairs+=1
            if soos.get("PF") and soos["PF"]>1: perpair_gt1+=1
        print(f"{p:<8}{sis.get('n',0):>5}{str(sis.get('PF','-')):>7}{soos.get('n',0):>6}"
              f"{str(soos.get('PF','-')):>8}{str(soos.get('expectancy_R','-')):>8}"
              f"{str(soos.get('win_rate','-')):>7}{str(soos.get('boot_P_PF<=1','-')):>8}"
              f"{str(s1.get('PF','-')):>7}{str(s2.get('PF','-')):>7}")
    POOL=np.concatenate(pool_oos) if pool_oos else np.array([])
    ps=rb.stats(POOL)
    print(f"{'POOL':<8}{'':>5}{'':>7}{ps.get('n',0):>6}{str(ps.get('PF','-')):>8}"
          f"{str(ps.get('expectancy_R','-')):>8}{str(ps.get('win_rate','-')):>7}{str(ps.get('boot_P_PF<=1','-')):>8}")
    crit1=(ps.get('PF') or 0)>1 and (ps.get('boot_P_PF<=1') is not None and ps['boot_P_PF<=1']<0.05)
    crit2=perpair_gt1>=int(0.7*max(npairs,1)+0.999)
    crit4=(ps.get('n') or 0)>=150
    print(f"[判定] プールPF>1&P<0.05={crit1}  ペア過半PF>1={perpair_gt1}/{npairs}  n>=150={crit4}")
    return {"k":k_required,"pool":ps,"perpair_gt1":perpair_gt1,"npairs":npairs}

if __name__=="__main__":
    out=[run(k) for k in (2,3,4)]
    json.dump(out, open("results/ensemble_meanrev.json","w"), indent=2, default=str)
    print("\n(日足10年・IS無調整・OOS後40%。合格はプールPF>1かつP<0.05かつペア一貫。)")
