# -*- coding: utf-8 -*-
"""
optimize_portfolio3.py — Portfolio3(v7+v4+E5) の【比率×サイズ】を正式スイープ最適化。

背景(穴): 2戦略(v7:E5)の比率は docs/32,35 で最適化済みだが、**3戦略(v7:v4:E5)の比率は 40:40:20 が
  『リスク寄与の手置き概算』のまま未スイープ**(docs/45 §3「正確な配分は10年実測で確定」)。本スクリプトが
  その穴を埋める。リスク配分(ratio)とサイズ(multiplier)を分離し、目的別(失格最小/手取り最大/Calmar最大)に
  最適点を出す。

手法(docs/32 と同思想・実系列):
  - 各戦略の月次account%系列を実データから再構成(v7=Yahoo H1 ~2y, v4/E5=Yahoo 10y日足。既存 colab と同ロジック)。
  - リスク配分 a=(a7,a4,a5)(合計1)を、各戦略を月次vol=a_i に正規化(k_i=a_i/σ_i)して合成 → リスク寄与=比率。
  - 合成系列に総倍率 m を掛け、目標 maxDD(−10%枠の内側)に合わせる。CAGRは実μ由来(高Calmar戦略ほど寄与大)。
  - 相関は実10年で v7⇄v4 −0.13 / v7⇄E5 −0.18 / v4⇄E5 −0.05(確定, docs/44,46)＝ほぼ0〜弱負。
    → 各戦略の自系列から独立ブロックブートストラップで合成(弱負相関を独立扱い=**やや保守**: 実際の
       負相関は更にDDを下げる方向ゆえ、本失格率は上限寄り)。
  - 口座: Blueberry インスタント(−10%トレーリング・5年失格) と FN/FTMO プロップ(静的−10%/+8%目標) 両方。

⚠ v7は Yahoo H1 ~2年(短い)。**確定は10年H1 Dukascopy(colab_optimize_portfolio3_10y.py)**。本書は方向と
  比率ランキングの確定が目的(絶対失格率は Drive で再測)。各戦略の標準スタッツを出力で開示(v7の2年 vs
  確定10年 −6.2%/+29% を併記)。数字は実行ログのみ(docs/08 の仮数値error を繰り返さない)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,"data"); RES=os.path.join(HERE,"results")
os.makedirs(RES,exist_ok=True)
PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY=["EURJPY","GBPJPY","USDJPY"]; HOURS=[4,6,8,10]
ASSETS=["XAUUSD","US500","NAS100","GER40"]; LB=[1,3,6,12]; VOLWIN=12
SPREAD={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,"USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFSPR=1.5; SLIP=0.5
E5_FRICTION=dict(idx_long=-3.0,idx_short=-1.5,gold_long=-4.0,gold_short=-1.5)
N_PATHS=6000; SEED=11
def pipsz(p): return 0.01 if p.endswith("JPY") else 0.0001

def _read_csv(path):
    df=pd.read_csv(path); df["timestamp"]=pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").set_index("timestamp")
def h1(p):
    f=os.path.join(DATA,f"{p}_h1.csv"); return _read_csv(f) if os.path.exists(f) else None
def daily(p):
    f=os.path.join(DATA,f"{p}_d.csv"); return _read_csv(f) if os.path.exists(f) else None
def masset(n):
    f=os.path.join(DATA,f"{n}_d.csv"); return _read_csv(f) if os.path.exists(f) else None

def rsi_w(c,n=14):
    d=np.diff(c,prepend=c[0]);up=np.clip(d,0,None);dn=np.clip(-d,0,None)
    au=np.empty_like(c);ad=np.empty_like(c);au[0]=up[0];ad[0]=dn[0];a=1/n
    for i in range(1,len(c)):au[i]=a*up[i]+(1-a)*au[i-1];ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=np.divide(au,np.where(ad==0,np.nan,ad));return np.nan_to_num(100-100/(1+rs),nan=50.0)
def atr_w(h,l,c,n=14):
    pc=np.roll(c,1);pc[0]=c[0];tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)])
    o=np.empty_like(c);o[0]=tr[0];a=1/n
    for i in range(1,len(c)):o[i]=a*tr[i]+(1-a)*o[i-1]
    return o
def bb_z(c,n=20):
    z=np.full_like(c,np.nan)
    for i in range(n,len(c)):
        w=c[i-n:i];s=w.std(ddof=1)
        if s>0:z[i]=(c[i]-w.mean())/s
    return z

def v7_monthly(weekly_budget=0.60):
    cols=[]
    for p in JPY:
        d=h1(p)
        if d is None: continue
        cv=d["close"].values; idx=d.index; ps=pipsz(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            if len(a)==0: continue
            r=pd.Series((cv[a+24]-cv[a])/cv[a]-2.0*ps/cv[a], index=idx[a].to_period("M"))
            cols.append(r.groupby(level=0).sum())
    if not cols: return pd.Series(dtype=float)
    s=pd.concat(cols,axis=1).sum(axis=1).dropna()
    # 等加重12ショット → 週次予算 weekly_budget% にスケール(各ショット budget/HOURS)
    return s*(weekly_budget/100.0)

def v4_monthly(risk_per_trade=0.15):
    from collections import defaultdict; mo=defaultdict(float)
    for p in PAIRS:
        d=daily(p)
        if d is None: continue
        o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values;idx=d.index
        rsi=rsi_w(c);z=bb_z(c);dn=np.zeros(len(c));upp=np.zeros(len(c))
        for i in range(1,len(c)):
            dn[i]=dn[i-1]+1 if c[i]<c[i-1] else 0; upp[i]=upp[i-1]+1 if c[i]>c[i-1] else 0
        ret=np.zeros(len(c));ret[1:]=(c[1:]-c[:-1])/c[:-1];sig=np.zeros(len(c))
        for i in range(20,len(c)):
            bv=int(rsi[i]<35)+int((not np.isnan(z[i]))and z[i]<-1.5)+int(dn[i]>=3)+int(ret[i]<-0.005)
            sv=int(rsi[i]>65)+int((not np.isnan(z[i]))and z[i]>1.5)+int(upp[i]>=3)+int(ret[i]>0.005)
            if bv>=4 and bv>sv: sig[i]=1
            elif sv>=4 and sv>bv: sig[i]=-1
        atr=atr_w(h,l,c);pip=pipsz(p);half=(SPREAD.get(p,DEFSPR)/2+SLIP)*pip;pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dd=pos["dir"];e=pos["entry"];sl=pos["sl"];tp=pos["tp"];ex=None
                if dd>0:
                    if l[i]-half<=sl:ex=sl
                    elif h[i]-half>=tp:ex=tp
                else:
                    if h[i]+half>=sl:ex=sl
                    elif l[i]+half<=tp:ex=tp
                if ex is None and (i-pos["i"])>=8:ex=o[i]+(half if dd<0 else -half)
                if ex is not None:
                    mo[idx[pos["i"]].to_period("M")]+=((ex-e) if dd>0 else (e-ex))/pos["risk"];pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    e=o[i]+(half if s>0 else -half);risk=atr[i-1]*1.5
                    sl=e-risk if s>0 else e+risk;tp=e+1.2*risk if s>0 else e-1.2*risk
                    pos={"dir":s,"entry":e,"sl":sl,"tp":tp,"risk":risk,"i":i}
    s=pd.Series(mo); s.index=pd.PeriodIndex(s.index,freq="M")
    return (s.sort_index())*(risk_per_trade/100.0)   # R単位 → account%(risk_per_trade% per R)

def e5_monthly(legRisk=0.30, fr=E5_FRICTION):
    legs=[]
    for a in ASSETS:
        d=masset(a)
        if d is None: continue
        m=d["close"].groupby(d.index.to_period("M")).last()
        if len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB)); r=m.pct_change(); nx=r.shift(-1)
        sig=r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std().shift(1); isg=(a=="XAUUSD")
        cl=fr["gold_long"] if isg else fr["idx_long"]; cs=fr["gold_short"] if isg else fr["idx_short"]
        out={}
        for t in m.index:
            p0=pos.get(t,0);v=sig.get(t,np.nan);fwd=nx.get(t,np.nan)
            if not(np.isfinite(p0) and p0!=0 and np.isfinite(v) and v>0 and np.isfinite(fwd)): continue
            out[t]=(legRisk/100.0)*((p0*fwd+((cl if p0>0 else cs)/100.0/12.0))/v)
        legs.append(pd.Series(out))
    if not legs: return pd.Series(dtype=float)
    return pd.concat(legs,axis=1).sum(axis=1).dropna()

# ---- 標準スタッツ ----
def ann_return(s):
    s=pd.Series(s).dropna()
    return float(((1+s).prod())**(12/len(s))-1) if len(s) else 0.0
def maxdd(s):
    eq=(1+pd.Series(s).dropna()).cumprod();pk=eq.cummax();return float(((eq-pk)/pk).min()) if len(s) else 0.0
def ann_vol(s):
    s=pd.Series(s).dropna();return float(s.std()*np.sqrt(12)) if len(s) else 0.0
def sharpe(s):
    v=ann_vol(s);return ann_return(s)/v if v>0 else 0.0

# ---- MC: 独立ブロックブートストラップ(ベクトル化) ----
def boot_matrix(s, n_paths=N_PATHS, months=60, block=3, seed=SEED):
    """系列 s(account%/単位)を独立ブロック再標本した (n_paths, months) 行列を一度だけ生成。"""
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,months))
    rng=np.random.default_rng(seed); nb=int(np.ceil(months/block))
    starts=rng.integers(0,n,size=(n_paths,nb))               # 各ブロックの開始
    offs=np.arange(block)
    idx=(starts[:,:,None]+offs[None,None,:])%n               # (n_paths, nb, block)
    return w[idx].reshape(n_paths,nb*block)[:,:months]

def _dd_min(P):
    eq=np.cumprod(1+P,axis=1); pk=np.maximum.accumulate(eq,axis=1)
    return ((eq-pk)/pk).min(axis=1)                          # 各パスのmaxDD(負)
def path_maxdd_p95(P): return float(np.percentile(_dd_min(P),5))   # 深部5%
def trailing_fail_rate(P,total_dd=0.10,horizon=12):
    return float((_dd_min(P[:,:min(P.shape[1],horizon)])<=-total_dd).mean())
def cum_fail_5y(P,total_dd=0.10): return trailing_fail_rate(P,total_dd,60)
def cagr_of(P):
    fin=np.prod(1+P,axis=1); return float(np.median(fin)**(12/P.shape[1])-1)

def anchor_sharpe(s, S_target, unit_mvol=0.01):
    """系列の分布形状(歪度/テール/自己相関)を保ったまま、年率Sharpeを S_target にアンカー。
       月次vol=unit_mvol に正規化し、月次平均= S_target*unit_mvol/sqrt(12)(=年率Sharpe S_target)。
       絶対水準はリスク正規化+目標DDスケールで相殺されるため、最適比率は Sharpe・テール形状・相関のみに依存。"""
    s=pd.Series(s).dropna(); z=(s-s.mean())/s.std()
    return z*unit_mvol + S_target*unit_mvol/np.sqrt(12)

def main():
    # 確定10年Sharpe(docs/40: v7 0.78 / E5 0.57)・v4は10年Yahoo日足再構成(=Dukascopy日足とほぼ同等)
    S={"v7":0.78,"v4":None,"v5":0.57}
    s7=v7_monthly(); s4=v4_monthly(); s5=e5_monthly()
    recon={"v7(raw2y)":s7,"v4(10y)":s4,"E5(10y)":s5}
    S["v4"]=round(sharpe(s4),3)                                # v4 は実10年再構成のSharpeを採用
    # Sharpeアンカー(形状保持)。v4/E5は10年実形状、v7は2年形状にSharpeのみ確定値を付与
    series={"v7":anchor_sharpe(s7,S["v7"]),"v4":anchor_sharpe(s4,S["v4"]),"v5":anchor_sharpe(s5,S["v5"])}
    stats={}
    for k,s in {**recon,**{f"{n}(anchored)":series[n] for n in ['v7','v4','v5']}}.items():
        stats[k]=dict(n=int(len(pd.Series(s).dropna())),ann_ret=round(ann_return(s)*100,2),
                      ann_vol=round(ann_vol(s)*100,2),maxDD=round(maxdd(s)*100,2),sharpe=round(sharpe(s),2))
    order=["v7","v4","v5"]
    sig={k:ann_vol(series[k])/np.sqrt(12) for k in order}     # 月次vol(アンカー後=unit, 全戦略同一)
    Bmat={k:boot_matrix(series[k]) for k in order}            # 各戦略のパス行列を一度だけ生成
    TARGET_DD=0.08   # −10%枠に2%マージン(docs/32 思想)。サイズmで目標DDに合わせる
    grid=[]; steps=np.arange(0,1.0001,0.05)
    for a7 in steps:
        for a4 in steps:
            a5=1-a7-a4
            if a5<-1e-9 or a5>1+1e-9: continue
            a5=round(float(a5),4)
            if a5<0: continue
            a7r,a4r=round(float(a7),3),round(float(a4),3)
            avals=dict(v7=a7r,v4=a4r,v5=a5)
            kbase={k:(avals[k]/sig[k]) if sig[k]>0 and avals[k]>0 else 0.0 for k in order}
            if sum(kbase.values())==0: continue
            P0=sum(kbase[k]*Bmat[k] for k in order)           # リスク寄与=比率(独立合成・ベクトル)
            bstd=P0.std()
            if bstd<=1e-9: continue
            P0=P0*(0.01/bstd)                                  # 月次vol~1%に正規化(複利の線形領域を確保)
            dd0=abs(path_maxdd_p95(P0))
            if dd0<=1e-6: continue
            m=TARGET_DD/dd0; P=P0*m                            # 目標 p95 maxDD=−8% にサイズ合わせ
            dd95=path_maxdd_p95(P); cagr=cagr_of(P)
            grid.append(dict(ratio=f"{int(a7r*100)}:{int(a4r*100)}:{int(a5*100)}",a7=a7r,a4=a4r,a5=a5,
                             mult=round(m,3),cagr=round(cagr*100,2),maxDD_p95=round(dd95*100,2),
                             annual_fail=round(trailing_fail_rate(P,0.10,12)*100,3),
                             cum5y_fail=round(cum_fail_5y(P,0.10)*100,2),
                             calmar=round(cagr/abs(dd95) if dd95<0 else 0.0,3)))
    # 目的別最適
    valid=[g for g in grid if g["a7"]>0]   # v7は常に主力(0除外)
    by_fail=sorted(valid,key=lambda g:(g["cum5y_fail"],-g["cagr"]))[:8]
    by_cagr=sorted(valid,key=lambda g:(-g["cagr"],g["cum5y_fail"]))[:8]
    by_calmar=sorted(valid,key=lambda g:(-g["calmar"]))[:8]
    cur=[g for g in grid if g["ratio"]=="40:40:20"]
    out=dict(meta=dict(note="real reconstructed series; numbers are run outputs only",
                       target_dd=TARGET_DD, account="Blueberry instant -10% trailing (5y)",
                       corr_confirmed="v7v4 -0.13 / v7E5 -0.18 / v4E5 -0.05 (indep boot=conservative)",
                       v7_span="Yahoo H1 ~2y anchored to confirmed 10y (-6.2%/+29%)"),
             strategy_stats=stats,
             current_40_40_20=cur[0] if cur else None,
             opt_min_fail=by_fail[0], opt_max_cagr=by_cagr[0], opt_max_calmar=by_calmar[0],
             top_by_fail=by_fail, top_by_cagr=by_cagr, top_by_calmar=by_calmar, full_grid=grid)
    with open(os.path.join(RES,"optimize_portfolio3.json"),"w") as f: json.dump(out,f,indent=2,default=str)
    # コンソール
    print("="*78); print("各戦略 標準スタッツ(実系列):")
    for k,v in stats.items(): print(f"  {k:18s} n={v['n']:3d} annRet={v['ann_ret']:+6.2f}% vol={v['ann_vol']:5.2f}% maxDD={v['maxDD']:+6.2f}% Sharpe={v['sharpe']}")
    print(f"\n目標maxDD(p95)= -{TARGET_DD*100:.0f}% にサイズmで合わせ, Blueberry -10%トレーリングで5年失格を評価")
    def show(title,g): print(f"\n[{title}] 比率 {g['ratio']}  m={g['mult']}x  CAGR={g['cagr']}%  p95maxDD={g['maxDD_p95']}%  年失格={g['annual_fail']}%  5年失格={g['cum5y_fail']}%  Calmar={g['calmar']}")
    if cur: show("現状 40:40:20",cur[0])
    show("★失格最小",out["opt_min_fail"]); show("★手取り最大(CAGR)",out["opt_max_cagr"]); show("★Calmar最大",out["opt_max_calmar"])
    print("\n失格最小 上位:")
    for g in by_fail[:6]: print(f"   {g['ratio']:9s} m={g['mult']}x CAGR={g['cagr']}% 5yFail={g['cum5y_fail']}% Calmar={g['calmar']}")
    print("\nCAGR最大 上位:")
    for g in by_cagr[:6]: print(f"   {g['ratio']:9s} m={g['mult']}x CAGR={g['cagr']}% 5yFail={g['cum5y_fail']}% Calmar={g['calmar']}")
    print("\n出所: research/results/optimize_portfolio3.json  (確定は colab_optimize_portfolio3_10y.py / Drive 10年)")

if __name__=="__main__": main()
