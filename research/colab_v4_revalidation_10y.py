"""
colab_v4_revalidation_10y.py — v4「k≥4 合議」を【ユーザーの実10年Dukascopy】で再測(探索補正付)。

位置づけ: research/v4_revalidation_10y.py は Yahoo日足10年で v4 を STRONG-LEAD(5/6, 唯一の不合格=
  探索補正Bonferroni perm_p0.0062 vs α0.0028) と採点し、v7と無相関(0.044)＝第3分散候補と判定した。
  本スクリプトは **Yahoo概算を排除**し、ユーザーDriveの10年Dukascopy H1 を日足にリサンプルして
  同一ゲート＋探索補正で再測する。Dukascopyに無いペアは Yahoo日足10y で補い、**出所をペア別に明示**する。

ゲート(v7基準, 日足10年): G3 OOS perm_p<Bonferroni(N=18,α=0.0028) / G4 placebo(ランダム同数で崩壊) /
  G5 疑似年次JK(10分割LOO max_p≤0.10) / G6 IS/OOS両+ / G7 WF(5分割でPF>1≥4) / G8 コスト2×。
  + k=2/3/4比較 ＋ v4↔v7月次相関(無相関なら第3分散として価値)。

使い方(Colab): USE_DRIVE=True。H1_DIR に {pair}_h1.csv(10年, UTC)。9ペア(EURUSD GBPUSD USDJPY AUDUSD
  USDCHF USDCAD NZDUSD EURJPY GBPJPY)。Driveに無いペアはYahoo自動取得(10y日足)。「すべて実行」。
※ シミュレーション。STRONG-LEADは未確証＝ADOPTはデモ前進検証(docs/29)で。将来/ライブ約定は保証しない。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; DAILY_DIR="{base}/dukascopy_data_d"; LOCAL_FALLBACK="./research/data"
PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY=["EURJPY","GBPJPY","USDJPY"]
SPREAD_PIPS={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,"USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFSPREAD=1.5; SLIP=0.5
N_TRIALS=18; BONF=0.05/N_TRIALS

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e: print("Drive不可:",e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

# ---------- データ: Dukascopy(日足 or H1→日足) 優先, 無ければYahoo日足 ----------
def _read(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*n):
        for x in n:
            for c in df.columns:
                if c.lower()==x: return c
        return None
    o=col("open","bidopen","o"); h=col("high","bidhigh","h"); l=col("low","bidlow","l"); c=col("close","bidclose","c")
    if None in (o,h,l,c): return None
    return df[[o,h,l,c]].astype(float).rename(columns={o:"open",h:"high",l:"low",c:"close"})

def _to_daily(df):
    g=df.resample("1D"); d=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),
        "low":g["low"].min(),"close":g["close"].last()}).dropna()
    return d

def _yahoo_daily(pair):
    import urllib.request, json as _json, datetime as _dt
    sym={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X","USDCHF":"USDCHF=X",
         "USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X"}[pair]
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=_json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
    ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[(pd.to_datetime(t,unit="s",utc=True),q["open"][i],q["high"][i],q["low"][i],q["close"][i])
          for i,t in enumerate(ts) if None not in (q["open"][i],q["high"][i],q["low"][i],q["close"][i])]
    df=pd.DataFrame(rows,columns=["t","open","high","low","close"]).set_index("t")
    return df

SOURCE={}
def load_daily(pair):
    # 1) Dukascopy 日足
    for p in [f"{DAILY_DIR.format(base=DRIVE_BASE)}/{pair}_d.csv", f"{DAILY_DIR.format(base=DRIVE_BASE)}/{pair}.csv"]:
        if os.path.exists(p):
            df=_read(p)
            if df is not None: SOURCE[pair]="Dukascopy-D"; return df
    # 2) Dukascopy H1 → 日足
    for p in [f"{H1_DIR.format(base=DRIVE_BASE)}/{pair}_h1.csv", f"{H1_DIR.format(base=DRIVE_BASE)}/{pair}.csv"]:
        if os.path.exists(p):
            df=_read(p)
            if df is not None: SOURCE[pair]="Dukascopy-H1→D"; return _to_daily(df)
    # 3) ローカルYahoo日足
    lp=f"{LOCAL_FALLBACK}/{pair}_d.csv"
    if os.path.exists(lp):
        df=_read(lp)
        if df is not None: SOURCE[pair]="local-Yahoo"; return df
    # 4) Yahoo取得
    try:
        df=_yahoo_daily(pair); SOURCE[pair]="Yahoo-fetch"; return df
    except Exception as e:
        print(f"  {pair} 取得失敗:{e}"); SOURCE[pair]="MISSING"; return None

# ---------- 指標(Wilder) ----------
def rsi_w(c,n=14):
    d=np.diff(c,prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    au=np.empty_like(c); ad=np.empty_like(c); au[0]=up[0]; ad[0]=dn[0]; a=1.0/n
    for i in range(1,len(c)): au[i]=a*up[i]+(1-a)*au[i-1]; ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=np.divide(au,np.where(ad==0,np.nan,ad)); return np.nan_to_num(100-100/(1+rs),nan=50.0)
def atr_w(h,l,c,n=14):
    pc=np.roll(c,1); pc[0]=c[0]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)])
    out=np.empty_like(c); out[0]=tr[0]; a=1.0/n
    for i in range(1,len(c)): out[i]=a*tr[i]+(1-a)*out[i-1]
    return out
def bb_z(c,n=20):
    z=np.full_like(c,np.nan)
    for i in range(n,len(c)):
        w=c[i-n:i]; s=w.std(ddof=1)
        if s>0: z[i]=(c[i]-w.mean())/s
    return z
def confluence(o,h,l,c,k):
    rsi=rsi_w(c,14); z=bb_z(c,20)
    down=np.zeros(len(c)); up=np.zeros(len(c))
    for i in range(1,len(c)):
        down[i]=down[i-1]+1 if c[i]<c[i-1] else 0
        up[i]=up[i-1]+1 if c[i]>c[i-1] else 0
    ret=np.zeros(len(c)); ret[1:]=(c[1:]-c[:-1])/c[:-1]; sig=np.zeros(len(c))
    for i in range(20,len(c)):
        zlo=(not np.isnan(z[i])) and z[i]<-1.5; zhi=(not np.isnan(z[i])) and z[i]>1.5
        bv=int(rsi[i]<35)+int(zlo)+int(down[i]>=3)+int(ret[i]<-0.005)
        sv=int(rsi[i]>65)+int(zhi)+int(up[i]>=3)+int(ret[i]>0.005)
        if bv>=k and bv>sv: sig[i]=1
        elif sv>=k and sv>bv: sig[i]=-1
    return sig

def simulate(pair,o,h,l,c,sig,sl_atr=1.5,rr=1.2,max_hold=8,cost_mult=1.0):
    pip=pip_size(pair); atr=atr_w(h,l,c,14)
    half=(SPREAD_PIPS.get(pair,DEFSPREAD)/2.0+SLIP*cost_mult)*pip*cost_mult if False else (SPREAD_PIPS.get(pair,DEFSPREAD)/2.0+SLIP)*pip*cost_mult
    R=[]; pos=None
    for i in range(1,len(c)):
        if pos is not None:
            dirn=pos["dir"];e=pos["entry"];sl=pos["sl"];tp=pos["tp"];hi=h[i];lo=l[i];ex=None
            if dirn>0:
                if lo-half<=sl: ex=sl
                elif hi-half>=tp: ex=tp
            else:
                if hi+half>=sl: ex=sl
                elif lo+half<=tp: ex=tp
            if ex is None and (i-pos["i"])>=max_hold: ex=o[i]+(half if dirn<0 else -half)
            if ex is not None:
                R.append(((ex-e) if dirn>0 else (e-ex))/pos["risk"]); pos=None
        if pos is None:
            s=sig[i-1]
            if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                e=o[i]+(half if s>0 else -half); risk=atr[i-1]*sl_atr
                sl=e-risk if s>0 else e+risk; tp=e+rr*risk if s>0 else e-rr*risk
                pos={"dir":s,"entry":e,"sl":sl,"tp":tp,"risk":risk,"i":i}
    return np.array(R,float)

# ---------- 統計 ----------
def pf(R):
    if len(R)==0: return 0.0
    gp=R[R>0].sum(); gl=-R[R<0].sum(); return gp/gl if gl>0 else float("inf")
def perm_p(R,n=5000,seed=11):
    if len(R)<10: return 1.0
    rng=np.random.default_rng(seed); real=R.sum(); a=np.abs(R)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())

DATA={}
def D(pair):
    if pair not in DATA: DATA[pair]=load_daily(pair)
    return DATA[pair]

def collect(k,a=0.0,b=1.0,cost_mult=1.0,placebo=False,seed=7):
    allR=[]; rng=np.random.default_rng(seed)
    for p in PAIRS:
        df=D(p)
        if df is None: continue
        o=df["open"].values;h=df["high"].values;l=df["low"].values;c=df["close"].values
        sig=confluence(o,h,l,c,k)
        if placebo:
            idx=np.where(sig!=0)[0]; m=len(idx); s2=np.zeros_like(sig)
            if m>0:
                pick=rng.choice(np.arange(20,len(c)-1),size=min(m,len(c)-25),replace=False)
                s2[pick]=rng.choice([-1,1],size=len(pick))
            sig=s2
        i,j=int(len(c)*a),int(len(c)*b)
        allR.append(simulate(p,o[i:j],h[i:j],l[i:j],c[i:j],sig[i:j],cost_mult=cost_mult))
    return np.concatenate(allR) if allR else np.array([])

def v4_monthly(k=4):
    from collections import defaultdict; mo=defaultdict(float)
    for p in PAIRS:
        df=D(p)
        if df is None: continue
        o=df["open"].values;h=df["high"].values;l=df["low"].values;c=df["close"].values
        idx=df.index; sig=confluence(o,h,l,c,k); pip=pip_size(p); atr=atr_w(h,l,c,14)
        half=(SPREAD_PIPS.get(p,DEFSPREAD)/2.0+SLIP)*pip; pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn=pos["dir"];e=pos["entry"];sl=pos["sl"];tp=pos["tp"];ex=None
                if dirn>0:
                    if l[i]-half<=sl: ex=sl
                    elif h[i]-half>=tp: ex=tp
                else:
                    if h[i]+half>=sl: ex=sl
                    elif l[i]+half<=tp: ex=tp
                if ex is None and (i-pos["i"])>=8: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    mo[str(idx[pos["i"]])[:7]]+=((ex-e) if dirn>0 else (e-ex))/pos["risk"]; pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    e=o[i]+(half if s>0 else -half); risk=atr[i-1]*1.5
                    sl=e-risk if s>0 else e+risk; tp=e+1.2*risk if s>0 else e-1.2*risk
                    pos={"dir":s,"entry":e,"sl":sl,"tp":tp,"risk":risk,"i":i}
    return mo
def v7_monthly():
    from collections import defaultdict; mo=defaultdict(float)
    for p in JPY:
        df=D(p)
        if df is None: continue
        o=df["open"].values; idx=df.index; pip=pip_size(p)
        cost=(SPREAD_PIPS.get(p,DEFSPREAD)+2*SLIP)*pip
        for i in range(len(o)-1):
            if idx[i].weekday()==0: mo[str(idx[i])[:7]]+=(o[i+1]-o[i])/o[i]-cost/o[i]
    return mo

def run():
    print("="*70); print(f"v4 k≥4 — 実10年再測(Dukascopy優先) v7基準＋探索補正 N={N_TRIALS} α={BONF:.4f}"); print("="*70)
    for p in PAIRS: D(p)
    print("データ出所:", {p:SOURCE.get(p) for p in PAIRS})
    sp=next((D(p).index for p in PAIRS if D(p) is not None),None)
    if sp is not None: print(f"期間: {sp.min().date()} .. {sp.max().date()}")
    print("\n--- k比較(全期間) ---")
    res={}
    for k in (2,3,4):
        R=collect(k); res[k]=dict(n=int(len(R)),PF=round(pf(R),3),exp=round(float(R.mean()) if len(R) else 0,4),perm_p=round(perm_p(R),4))
        print(f"  k≥{k}: n={res[k]['n']:5d} PF={res[k]['PF']:.3f} exp={res[k]['exp']:+.4f}R perm_p={res[k]['perm_p']:.4f}")
    K=4; Rf=collect(K); Ris=collect(K,0,0.6); Ro=collect(K,0.6,1.0)
    oosp=perm_p(Ro); Rpl=collect(K,placebo=True)
    jk=[]
    for d in range(10):
        a=d/10.0; b=(d+1)/10.0
        Rk=np.concatenate([collect(K,0,a),collect(K,b,1.0)]) if 0<d<9 else (collect(K,b,1.0) if d==0 else collect(K,0,a))
        jk.append(perm_p(Rk))
    jkmax=max(jk); wf=sum(1 for s in range(5) if pf(collect(K,s/5.0,(s+1)/5.0))>1.0); R2=collect(K,cost_mult=2.0)
    g={"G3_perm_bonf":oosp<BONF,"G4_placebo":pf(Ro)>pf(Rpl) and (Ro.mean() if len(Ro) else 0)>(Rpl.mean() if len(Rpl) else 0),
       "G5_jackknife":jkmax<=0.10,"G6_IS_OOS":Ris.sum()>0 and Ro.sum()>0,"G7_wf":wf>=4,"G8_cost2x":pf(R2)>1.0 and (R2.mean() if len(R2) else 0)>0}
    print(f"\n--- k≥4 ゲート ---")
    print(f"  全期間PF={pf(Rf):.3f} OOS PF={pf(Ro):.3f} OOS perm_p={oosp:.4f}(Bonf {BONF:.4f}) placebo PF={pf(Rpl):.3f}")
    print(f"  G3permBonf:{g['G3_perm_bonf']} G4placebo:{g['G4_placebo']} G5JK(max{jkmax:.3f}):{g['G5_jackknife']} G6IS/OOS:{g['G6_IS_OOS']} G7WF({wf}/5):{g['G7_wf']} G8cost2x:{g['G8_cost2x']}")
    passed=sum(1 for v in g.values() if v)
    grade="ADOPT" if all(g.values()) else ("STRONG-LEAD" if (g["G4_placebo"] and g["G6_IS_OOS"] and g["G7_wf"] and g["G8_cost2x"]) else "LEAD/REJECT")
    # 相関
    m4=v4_monthly(); m7=v7_monthly(); keys=sorted(set(m4)&set(m7))
    corr=round(float(np.corrcoef([m4[k] for k in keys],[m7[k] for k in keys])[0,1]),3) if len(keys)>=12 else None
    print(f"\n  v4↔v7 月次相関={corr} (共通{len(keys)}ヶ月)")
    print(f"  → {passed}/6 / 判定 {grade}")
    if not g["G3_perm_bonf"]:
        print(f"     ※OOS perm_p={oosp:.4f} は探索補正α={BONF:.4f}に未達＝Yahoo版と同じ『探索生存者』懸念（実Dukascopyでも）")
    out=dict(sources={p:SOURCE.get(p) for p in PAIRS},N_trials=N_TRIALS,bonf=BONF,k_compare=res,corr_v4_v7=corr,
             k4=dict(full_PF=round(pf(Rf),3),oos_PF=round(pf(Ro),3),oos_perm_p=round(oosp,4),jk_max=round(jkmax,4),wf=f"{wf}/5",placebo_PF=round(pf(Rpl),3),gates=g,grade=grade))
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v4_revalidation_dukascopy.json") if DRIVE_OK else "research/results/v4_revalidation_dukascopy.json"
        os.makedirs(os.path.dirname(path),exist_ok=True); json.dump(out,open(path,"w"),ensure_ascii=False,indent=2,default=str); print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
