# -*- coding: utf-8 -*-
"""
validate_s3.py
==============
S3 RSI平均回帰(逆張り)のロバスト性検証。過剰最適化でないかを厳しく見る。

(A) パラメータ感度: RSIしきい値 / RSI期間 / SL_atr / RR を格子で振り、
    OOSプールPFの分布を見る。「特定の1点だけ良い」ならカーブフィット。
(B) ウォークフォワード: 年次OOS窓を複数作り、各窓のプールPFを並べる。
(C) Bonferroni: 試した戦略タイプ数(5)×主要パラメータ探索を考慮した保守的α。
全てプール集計(全ペア結合)で評価。
"""
import os, json, itertools
import numpy as np
import research_backtester as rb

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
RESULTS=os.path.join(os.path.dirname(__file__),"results")


def rsi_meanrev(c, n, lo, hi):
    rsi=rb.rsi_wilder(c,n); sig=np.zeros(len(c))
    sig[rsi<lo]=1; sig[rsi>hi]=-1
    return sig


def pooled_oos_R(n, lo, hi, sl_atr, rr, max_hold, frac=0.7):
    allR=[]
    for pair in PAIRS:
        ts,o,h,l,c=rb.load_daily(pair)
        sig=rsi_meanrev(c,n,lo,hi)
        cut=int(len(c)*frac)
        R=rb.simulate(pair,o[cut:],h[cut:],l[cut:],c[cut:],sig[cut:],
                      sl_atr=sl_atr,rr=rr,max_hold=max_hold)
        allR.append(R)
    return np.concatenate(allR) if allR else np.array([])


def pooled_R_window(n, lo, hi, sl_atr, rr, max_hold, start_frac, end_frac):
    allR=[]
    for pair in PAIRS:
        ts,o,h,l,c=rb.load_daily(pair)
        sig=rsi_meanrev(c,n,lo,hi)
        a=int(len(c)*start_frac); b=int(len(c)*end_frac)
        R=rb.simulate(pair,o[a:b],h[a:b],l[a:b],c[a:b],sig[a:b],
                      sl_atr=sl_atr,rr=rr,max_hold=max_hold)
        allR.append(R)
    return np.concatenate(allR) if allR else np.array([])


def main():
    out={}

    # (A) パラメータ感度格子
    print("=== (A) パラメータ感度 (OOS=後30%プール) ===")
    print(f"{'n':>3}{'lo':>4}{'hi':>4}{'sl':>5}{'rr':>5}{'N':>6}{'PF':>7}{'exp':>8}{'WR':>7}{'P(PF<=1)':>10}")
    grid=[]
    pos=0; tot=0
    for n in (10,14):
        for lo,hi in ((25,75),(30,70),(35,65)):
            for sl_atr in (1.5,2.0):
                for rr in (1.0,1.5,2.0):
                    R=pooled_oos_R(n,lo,hi,sl_atr,rr,max_hold=10)
                    s=rb.stats(R)
                    pf=s.get("PF",float("nan")); p=s.get("boot_P_PF<=1",float("nan"))
                    tot+=1
                    if isinstance(pf,float) and pf>1: pos+=1
                    print(f"{n:>3}{lo:>4}{hi:>4}{sl_atr:>5}{rr:>5}{s.get('n',0):>6}"
                          f"{pf:>7}{s.get('expectancy_R',float('nan')):>8}{s.get('win_rate',float('nan')):>7}{p:>10}")
                    grid.append({"n":n,"lo":lo,"hi":hi,"sl_atr":sl_atr,"rr":rr,**s})
    print(f"\n→ 格子{tot}点中 OOS_PF>1 は {pos}点 ({100*pos/tot:.0f}%)。"
          f" 大半でPF>1なら頑健(単一点のカーブフィットでない)。")
    out["sensitivity"]={"grid":grid,"pf_gt1_frac":pos/tot}

    # (B) ウォークフォワード(年次窓 近似: 10年を5つの20%窓)
    print("\n=== (B) ウォークフォワード窓 (基準: n=14,lo=30,hi=70,sl=1.5,rr=1.5) ===")
    print(f"{'window':>14}{'N':>6}{'PF':>7}{'exp':>8}{'WR':>7}{'P(PF<=1)':>10}")
    wins=[]
    edges=[(0.0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0)]
    for a,b in edges:
        R=pooled_R_window(14,30,70,1.5,1.5,10,a,b)
        s=rb.stats(R)
        print(f"{f'{int(a*100)}-{int(b*100)}%':>14}{s.get('n',0):>6}{s.get('PF',float('nan')):>7}"
              f"{s.get('expectancy_R',float('nan')):>8}{s.get('win_rate',float('nan')):>7}{s.get('boot_P_PF<=1',float('nan')):>10}")
        wins.append({"window":f"{a}-{b}",**s})
    pf_pos=sum(1 for w in wins if isinstance(w.get("PF"),float) and w["PF"]>1)
    print(f"\n→ {len(edges)}窓中 PF>1 は {pf_pos}窓。多数で>1なら時間的に頑健。")
    out["walkforward"]={"windows":wins,"pf_gt1_windows":pf_pos}

    # (C) Bonferroni
    n_tests=5*6  # 戦略タイプ5 × S3で実質探索した代表点6 程度の保守的見積り
    alpha=0.05/n_tests
    R=pooled_oos_R(14,30,70,1.5,1.5,10)
    s=rb.stats(R)
    p=s.get("boot_P_PF<=1",float("nan"))
    print("\n=== (C) Bonferroni 保守判定 ===")
    print(f"基準設定 OOSプール: PF={s.get('PF')}, exp={s.get('expectancy_R')}R, "
          f"WR={s.get('win_rate')}, n={s.get('n')}, P(PF<=1)={p}")
    print(f"想定試行数={n_tests}, 補正α={alpha:.5f}, 判定={'PASS' if (isinstance(p,float) and p<alpha) else 'FAIL'}")
    out["bonferroni"]={"alpha":alpha,"p":p,"pass":bool(isinstance(p,float) and p<alpha),"base":s}

    with open(os.path.join(RESULTS,"validate_s3.json"),"w") as f:
        json.dump(out,f,indent=2,default=str)


if __name__=="__main__":
    main()
