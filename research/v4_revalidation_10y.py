# -*- coding: utf-8 -*-
"""
v4_revalidation_10y.py — v4「多信号アンサンブル k≥4」を v7基準＋探索補正で10年再検定。

背景: docs/08 で k≥4 合議は「初めてプールで統計的有意(P=0.006)」に到達したが、
  (1)探索の生存者(k=2/3/4を試した中の当たり), (2)直近減衰, (3)取引希少 の但し書きで
  ADOPT保留＝「唯一筋がある次手」とされた。本スクリプトはユーザー要望に応え、
  **探索補正(Bonferroni)込みの v7基準ゲート**で k≥4 が本当に生き残るかを正直に採点する。

ゲート(v7基準・日足10年):
  G3' プールOOS perm_p < Bonferroni α(探索補正)   G6 IS/OOS両方+
  G4' プラセボ(ランダム同数エントリー)で崩れるか    G7 ウォークフォワード(5分割で PF>1 ≥4)
  G5' 疑似年次JK(10分割LOO)で符号安定              G8 コスト2×でもPF>1 / 期待値>0
  + 取引頻度(年あたり件数)・k=2/3/4比較

探索補正 N: docs/08 準拠で「v1〜v4 延べ~15戦略 + k=2/3/4」を計上 → α=0.05/18≈0.0028(保守)。
データ: research/data/{pair}_d.csv(日足10年, Yahoo)。最終判定はユーザーDukascopyで。誇張しない。
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_backtester as rb
import ensemble_meanrev as em

PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
N_TRIALS=18                      # 探索補正母数(v1-v4 ~15 + k=2/3/4)
BONF=0.05/N_TRIALS               # ≈0.0028

def pf(R):
    if len(R)==0: return 0.0
    gp=R[R>0].sum(); gl=-R[R<0].sum(); return gp/gl if gl>0 else float("inf")
def expectancy(R): return float(R.mean()) if len(R) else 0.0
def perm_p_mean(R, n=5000, seed=11):
    if len(R)<10: return 1.0
    rng=np.random.default_rng(seed); real=R.sum(); a=np.abs(R)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())

def trades_for(pair, k, seg=(0.0,1.0)):
    days,o,h,l,c = (None,)+rb.load_daily(pair)[1:] if False else (None,)+(None,)  # placeholder
    return None

def collect(k, a=0.0, b=1.0, cost_mult=1.0, placebo=False, seed=7):
    """全ペアの k≥k 合議トレードRを区間[a,b]で集めてプール。placebo=同数ランダム日。"""
    save_slip=rb.SLIPPAGE_PIPS; rb.SLIPPAGE_PIPS=save_slip*cost_mult
    allR=[]
    rng=np.random.default_rng(seed)
    try:
        for p in PAIRS:
            ts,o,h,l,c = rb.load_daily(p)
            sig=em.signals_confluence(o,h,l,c,k_required=k)
            if placebo:
                idx=np.where(sig!=0)[0]; nsig=len(idx)
                sig2=np.zeros_like(sig)
                if nsig>0:
                    pick=rng.choice(np.arange(20,len(c)-1), size=min(nsig,len(c)-25), replace=False)
                    dirs=rng.choice([-1,1], size=len(pick))
                    sig2[pick]=dirs
                sig=sig2
            i,j=int(len(c)*a),int(len(c)*b)
            R=rb.simulate(p,o[i:j],h[i:j],l[i:j],c[i:j],sig[i:j],sl_atr=1.5,rr=1.2,max_hold=8)
            allR.append(R)
    finally:
        rb.SLIPPAGE_PIPS=save_slip
    return np.concatenate(allR) if allR else np.array([])

def v4_monthly_pnl(k=4):
    """k≥k 合議トレードの実コスト後Rを、エントリー月で集計した月次P&L(全ペア合算)。"""
    from collections import defaultdict
    monthly=defaultdict(float)
    for p in PAIRS:
        ts,o,h,l,c=rb.load_daily(p)
        sig=em.signals_confluence(o,h,l,c,k_required=k)
        pip=rb.pip_size(p); atr=rb.atr_wilder(h,l,c,14)
        half=(rb.SPREAD_PIPS.get(p,rb.DEFAULT_SPREAD)/2.0+rb.SLIPPAGE_PIPS)*pip
        pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn=pos["dir"];entry=pos["entry"];sl=pos["sl"];tp=pos["tp"];hi=h[i];lo=l[i];ex=None
                if dirn>0:
                    if lo-half<=sl: ex=sl
                    elif hi-half>=tp: ex=tp
                else:
                    if hi+half>=sl: ex=sl
                    elif lo+half<=tp: ex=tp
                if ex is None and (i-pos["i"])>=8: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    r=((ex-entry) if dirn>0 else (entry-ex))/pos["risk"]
                    monthly[str(ts[pos["i"]])[:7]]+=r; pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    entry=o[i]+(half if s>0 else -half); risk=atr[i-1]*1.5
                    sl=entry-risk if s>0 else entry+risk; tp=entry+1.2*risk if s>0 else entry-1.2*risk
                    pos={"dir":s,"entry":entry,"sl":sl,"tp":tp,"risk":risk,"i":i}
    return monthly

def v7_monthly_proxy():
    """v7プロキシ: 各ペア 月曜の日足 open→翌営業日 open(LONG, 実コスト後)を月次合算。"""
    from collections import defaultdict
    import datetime as _dt
    monthly=defaultdict(float)
    for p in ["EURJPY","GBPJPY","USDJPY"]:
        ts,o,h,l,c=rb.load_daily(p); pip=rb.pip_size(p)
        cost=(rb.SPREAD_PIPS.get(p,rb.DEFAULT_SPREAD)+2*rb.SLIPPAGE_PIPS)*pip
        for i in range(len(o)-1):
            d=_dt.date.fromisoformat(str(ts[i])[:10])
            if d.weekday()==0:
                monthly[str(ts[i])[:7]]+=(o[i+1]-o[i])/o[i]-cost/o[i]
    return monthly

def corr_v4_v7():
    import numpy as _np
    m4=v4_monthly_pnl(4); m7=v7_monthly_proxy()
    keys=sorted(set(m4)&set(m7))
    if len(keys)<12: return None,len(keys)
    a=_np.array([m4[k] for k in keys]); b=_np.array([m7[k] for k in keys])
    return round(float(_np.corrcoef(a,b)[0,1]),3), len(keys)

def main():
    print("="*70); print(f"v4 k≥4 アンサンブル 10年再検定（v7基準＋探索補正 N={N_TRIALS}, α={BONF:.4f}）"); print("="*70)
    span=rb.load_daily("EURUSD")[0]; print(f"日足: {span[0]} .. {span[-1]}  ({len(span)}本)\n")

    # k比較(full)
    print("--- k比較(全期間プール) ---")
    res={}
    for k in (2,3,4):
        R=collect(k)
        res[k]=dict(n=int(len(R)), PF=round(pf(R),3), exp_R=round(expectancy(R),4),
                    wr=round(float((R>0).mean()),3) if len(R) else 0.0, perm_p=round(perm_p_mean(R),4))
        print(f"  k≥{k}: n={res[k]['n']:5d} PF={res[k]['PF']:.3f} exp={res[k]['exp_R']:+.4f}R "
              f"wr={res[k]['wr']:.3f} perm_p={res[k]['perm_p']:.4f}")

    K=4
    print(f"\n--- k≥{K} 詳細ゲート ---")
    Rfull=collect(K); Ris=collect(K,0.0,0.6); Roos=collect(K,0.6,1.0)
    yrs=len(span)/252.0; per_year=len(Rfull)/yrs
    g={}
    # G3' OOS perm_p < Bonf
    oos_p=perm_p_mean(Roos); g["G3_perm_bonf"]=(oos_p<BONF)
    # G4' placebo
    Rplac=collect(K,placebo=True); plac_pf=pf(Rplac)
    g["G4_placebo"]=(pf(Roos)>plac_pf and expectancy(Roos)>expectancy(Rplac))
    # G5' 疑似年次JK(10分割LOO, perm_p≤0.10 維持)
    jkps=[]
    for d in range(10):
        a=d/10.0; b=(d+1)/10.0
        # drop segment d
        Rkeep=np.concatenate([collect(K,0.0,a), collect(K,b,1.0)]) if d>0 and d<9 else (collect(K,b,1.0) if d==0 else collect(K,0.0,a))
        jkps.append(perm_p_mean(Rkeep))
    jkmax=max(jkps); g["G5_jackknife"]=(jkmax<=0.10)
    # G6 IS/OOS
    g["G6_IS_OOS"]=(Ris.sum()>0 and Roos.sum()>0)
    # G7 walk-forward 5分割
    wf=0
    for s in range(5):
        Rseg=collect(K, s/5.0, (s+1)/5.0)
        if pf(Rseg)>1.0: wf+=1
    g["G7_walkforward"]=(wf>=4)
    # G8 コスト2×
    R2=collect(K,cost_mult=2.0); g["G8_cost2x"]=(pf(R2)>1.0 and expectancy(R2)>0)

    print(f"  全期間 PF={pf(Rfull):.3f} exp={expectancy(Rfull):+.4f}R n={len(Rfull)} (~{per_year:.0f}件/年)")
    print(f"  OOS(後40%) PF={pf(Roos):.3f} exp={expectancy(Roos):+.4f}R perm_p={oos_p:.4f} (Bonf {BONF:.4f})")
    print(f"  IS(前60%) PF={pf(Ris):.3f} netR={Ris.sum():+.2f}  OOS netR={Roos.sum():+.2f}")
    print(f"  placebo PF={plac_pf:.3f} exp={expectancy(Rplac):+.4f}R")
    print(f"  G3_permBonf:{g['G3_perm_bonf']}  G4_placebo:{g['G4_placebo']}  G5_JK(max{jkmax:.3f}):{g['G5_jackknife']}")
    print(f"  G6_IS/OOS:{g['G6_IS_OOS']}  G7_WF({wf}/5):{g['G7_walkforward']}  G8_cost2x:{g['G8_cost2x']}")
    passed=sum(1 for v in g.values() if v)
    core_adopt=all([g["G3_perm_bonf"],g["G4_placebo"],g["G5_jackknife"],g["G6_IS_OOS"],g["G7_walkforward"],g["G8_cost2x"]])
    grade="ADOPT" if core_adopt else ("STRONG-LEAD" if (g["G4_placebo"] and g["G6_IS_OOS"] and g["G7_walkforward"] and g["G8_cost2x"]) else "LEAD/REJECT")
    print(f"\n  → {passed}/6 ゲート / 判定: {grade}")
    if not g["G3_perm_bonf"]:
        print(f"     ※OOS perm_p={oos_p:.4f} は探索補正α={BONF:.4f}に未達＝docs/08の『探索生存者』懸念が10年でも残存")

    cv,nm=corr_v4_v7()
    print(f"\n--- v4↔v7 月次相関 ---\n  corr={cv} (共通{nm}ヶ月)  "
          f"{'→低相関=有用な第3分散候補' if (cv is not None and abs(cv)<0.3) else '→高相関なら冗長'}")

    out={"span":[str(span[0]),str(span[-1])],"N_trials":N_TRIALS,"bonf":BONF,"corr_v4_v7":cv,"k_compare":res,
         "k4":{"full_PF":round(pf(Rfull),3),"oos_PF":round(pf(Roos),3),"oos_perm_p":round(oos_p,4),
               "per_year":round(per_year,1),"jk_max_p":round(jkmax,4),"wf":f"{wf}/5",
               "placebo_PF":round(plac_pf,3),"gates":g,"grade":grade}}
    with open(os.path.join(os.path.dirname(__file__),"results","v4_revalidation_10y.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    print("\n保存: research/results/v4_revalidation_10y.json")

if __name__=="__main__":
    main()
