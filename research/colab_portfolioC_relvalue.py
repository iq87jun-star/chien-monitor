# -*- coding: utf-8 -*-
"""
colab_portfolioC_relvalue.py — 第2(並走)ポート C案【新フレームワーク=リラティブバリュー(統計的ペア)】。

背景: docs/52 で「機構を別ユニバースへ」(v1+スイープ)は合格ゼロ＝この相場に第2の独立"方向性"エッジは無い、と確定。
  ユーザー選択「C.新フレームワーク探索」に従い、本プロジェクト未踏の枠組み=**リラティブバリュー
  (2資産スプレッドの平均回帰／コインテグレーション)** を9ゲートで一から検証する。
  これは「単一資産の方向」ではなく「2資産の相対価格(スプレッド)のzスコア平均回帰」を取る別機構で、
  カレンダー(v7)・トレンド(E5)・単一資産MR(v4)のいずれとも独立しやすい(=並走候補の最後の有望株)。

機構(ノールックアヘッド):
  各ペア(A,B)で log-spread_t = logA_t − β·logB_t (βは過去W日の回帰・t−1まで)。
  z_t=(spread−rollmean)/rollstd (t−1まで)。z>+Zで割高→スプレッドSHORT(A売/B買)、z<−Zで割安→LONG。
  |z|<Zexitで手仕舞い。日次スプレッド損益を実コスト後で月次集計。方向プラセボ(同機会・ランダム符号)も評価。

事前登録ペア(N=len(PAIRS)・経済的整合): 金銀比/豪NZ/欧州メジャー/米指数/transatlantic 等。
Bonferroni α=0.05/N。採点は現行と同一9ゲート＋現行(v7/v4maj/E5base)相関。合格=STRONG-LEAD以上＋相関<0.3＋p95DD≥−10%。

使い方(Colab): USE_DRIVE=True。FXはH1(dukascopy)優先→無ければYahoo日足。指数/金属はYahoo日足自動取得。「すべて実行」。
⚠ シミュレーション(Yahoo=配当/限月未精緻)。リラティブバリューは執行/借株/相関崩壊リスク大→確証はデモ(docs/29)。数字は盛らない。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

# ===== 事前登録ペア(A,B,Aがfx,Bがfx) — 経済的に共和分が期待される組 =====
PAIRS = [
  ("XAUUSD","XAGUSD",False,False),   # 金銀比(古典的レシオ平均回帰)
  ("AUDUSD","NZDUSD",True, True),    # 豪NZ(資源国・中銀近接)
  ("EURUSD","GBPUSD",True, True),    # 欧州メジャー
  ("US500","NAS100", False,False),   # 米株指数(大型vsハイテク)
  ("US500","GER40",  False,False),   # 米独株(transatlantic)
  ("XAUUSD","AUDUSD",False,True),    # 金 vs 資源通貨
  ("EURUSD","USDCHF",True, True),    # EUR vs CHF(逆相関の歴史)
]
# 現行(相関比較対象)
P1_V7_YEN  = ["EURJPY","GBPJPY","USDJPY"]
P1_V4_MAJ  = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
P1_E5_BASE = ["XAUUSD","US500","NAS100","GER40"]

_YH={"XAUUSD":"GC=F","XAGUSD":"SI=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def yahoo_of(name, fx):
    if name in _YH: return _YH[name]
    if fx and len(name)==6 and name.isalpha(): return name+"=X"
    return None

# RVパラメータ(事前固定・最適化しない)
W_BETA=120; W_Z=60; Z_ENTRY=2.0; Z_EXIT=0.5; COST_BPS=4.0
LB=[1,3,6,12]; VOLWIN=12; HOURS=[4,6,8,10]; COST_PIP=2.0
V4_RSI=14; V4_RSIlo=35.0; V4_RSIhi=65.0; V4_BBwin=20; V4_BBz=1.5; V4_STREAK=3
V4_DAYMOVE=0.005; V4_ATR=14; V4_SLATR=1.5; V4_RR=1.2; V4_HOLD=8
N=len(PAIRS); BONF=0.05/N
N_PATHS=4000; SEED=11; RV_LEGRISK=0.30

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")
def pip_size(p): return 0.01 if (len(p)>=6 and p.endswith("JPY")) else 0.0001

# ---------- データ ----------
def _h1_path(name):
    for x in [f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"]:
        if os.path.exists(x): return x
    return None
def _daily_path(name):
    for x in [f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]:
        if os.path.exists(x): return x
    return None
def _read(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    return df.dropna(subset=["t"]).sort_values("t").set_index("t")
def _col(df,*names):
    for n in names:
        if n in df.columns: return df[n].astype(float)
    return None
def fetch_yahoo_daily(name, fx):
    yh=yahoo_of(name, fx)
    if yh is None or _daily_path(name) is not None: return
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out_dir,exist_ok=True)
    try:
        u=f"https://query2.finance.yahoo.com/v8/finance/chart/{yh}?interval=1d&range=10y"
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
        d=_json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
        ts=r["timestamp"]; q=r["indicators"]["quote"][0]
        with open(os.path.join(out_dir,f"{name}_d.csv"),"w",newline="") as f:
            w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
            for i,t in enumerate(ts):
                o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                if None in (o,h,l,c): continue
                w.writerow([_dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
        print(f"  [取得] {name} ({yh})"); time.sleep(0.7)
    except Exception as e: print(f"  [取得失敗] {name}({yh}): {str(e)[:40]}")
CACHE={}
def daily_close(name, fx):
    if ("c",name) in CACHE: return CACHE[("c",name)]
    s=None
    if fx:
        p=_h1_path(name)
        if p is not None:
            d=_read(p); c=_col(d,"close","bidclose","c")
            if c is not None: s=c.resample("1D").last().dropna()
    if s is None:
        if _daily_path(name) is None: fetch_yahoo_daily(name, fx)
        p=_daily_path(name)
        if p is not None:
            d=_read(p); c=_col(d,"close","c")
            if c is not None: s=c.dropna()
    CACHE[("c",name)]=s; return s
def daily_ohlc_fx(name):  # v4機構用(FX日足OHLC)
    if ("o",name) in CACHE: return CACHE[("o",name)]
    df=None; p=_h1_path(name)
    if p is not None:
        d=_read(p); o=_col(d,"open","bidopen","o"); h=_col(d,"high","bidhigh","h"); l=_col(d,"low","bidlow","l"); c=_col(d,"close","bidclose","c")
        if c is not None:
            df=pd.DataFrame({"o":o if o is not None else c,"h":h if h is not None else c,"l":l if l is not None else c,"c":c}).resample("1D").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    if df is None:
        if _daily_path(name) is None: fetch_yahoo_daily(name, True)
        p=_daily_path(name)
        if p is not None:
            d=_read(p); o=_col(d,"open","o"); h=_col(d,"high","h"); l=_col(d,"low","l"); c=_col(d,"close","c")
            if c is not None: df=pd.DataFrame({"o":o if o is not None else c,"h":h if h is not None else c,"l":l if l is not None else c,"c":c}).dropna()
    CACHE[("o",name)]=df; return df

# ---------- RV(スプレッド平均回帰) ----------
def rv_monthly(A,B,fxA,fxB, cost_bps=COST_BPS, randomize=False, seed=7, legrisk=None):
    a=daily_close(A,fxA); b=daily_close(B,fxB)
    if a is None or b is None: return pd.Series(dtype=float)
    df=pd.concat([np.log(a).rename("la"), np.log(b).rename("lb")],axis=1).dropna()
    if len(df)<W_BETA+W_Z+30: return pd.Series(dtype=float)
    la=df["la"]; lb=df["lb"]
    # 過去W_BETA日の回帰β(t−1まで・ローリング)
    beta=pd.Series(index=df.index,dtype=float)
    cov=la.rolling(W_BETA).cov(lb); var=lb.rolling(W_BETA).var()
    beta=(cov/var).shift(1)            # t−1まで
    spread=la-beta*lb
    mu=spread.rolling(W_Z).mean().shift(1); sd=spread.rolling(W_Z).std().shift(1)
    z=((spread - mu)/sd).shift(1)      # シグナルはt−1のz(ノールックアヘッド)
    rng=np.random.default_rng(seed)
    # ポジション(zルール): z>+Z→spread short(-1), z<-Z→long(+1), |z|<Zexit→0(継続保持はholdで)
    pos=pd.Series(0.0,index=df.index); cur=0.0
    zv=z.values
    for i in range(len(df)):
        zi=zv[i]
        if np.isnan(zi): pos.iloc[i]=0.0; continue
        if cur==0.0:
            if zi>Z_ENTRY: cur=-1.0
            elif zi<-Z_ENTRY: cur=1.0
        else:
            if abs(zi)<Z_EXIT: cur=0.0
            elif cur>0 and zi>Z_ENTRY: cur=-1.0
            elif cur<0 and zi<-Z_ENTRY: cur=1.0
        pos.iloc[i]=cur
    if randomize:                      # 整合プラセボ=建玉する日に符号ランダム
        mask=(pos!=0).values; rp=pos.copy().values
        rp[mask]=rng.choice([-1.0,1.0],size=int(mask.sum())); pos=pd.Series(rp,index=df.index)
    # スプレッド日次リターン r = dla - β*dlb、損益= pos_{t-1}*r、コストは建玉変化×(両レッグbps)
    dla=la.diff(); dlb=lb.diff(); beta_f=beta.fillna(0.0)
    rspread=(dla - beta_f*dlb)
    turn=pos.diff().abs().fillna(pos.abs())
    cost=turn*(1.0+beta_f.abs())*(cost_bps/1e4)
    pnl=(pos.shift(1).fillna(0.0)*rspread - cost).dropna()
    m=pnl.groupby(pnl.index.to_period("M")).sum(); m.index=m.index.to_timestamp()
    m=m.dropna()
    if legrisk is not None and m.std()>0: m=m/m.std()*(legrisk/100.0)
    return m

# ---------- 現行系列(相関用・v7/v4/E5) ----------
def v7_monthly_proxy():
    from collections import defaultdict
    monthly=defaultdict(float)
    for p in P1_V7_YEN:
        ph=_h1_path(p)
        if ph is None: continue
        d=_read(ph); c=_col(d,"close","bidclose","c")
        if c is None: continue
        cv=c.values; idx=c.index; ps=pip_size(p)
        for h in HOURS:
            aa=np.where((idx.dayofweek==0)&(idx.hour==h))[0]; aa=aa[aa+24<len(cv)]
            for k in aa: monthly[str(idx[k])[:7]]+=(cv[k+24]-cv[k])/cv[k]-COST_PIP*ps/cv[k]
    s=pd.Series(monthly).sort_index()
    if len(s): s.index=pd.to_datetime(s.index+"-01")
    return s
def _wrsi(c,n=14):
    d=np.diff(c,prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    ru=np.full_like(c,np.nan); rd=np.full_like(c,np.nan)
    if len(c)<=n: return np.full_like(c,50.0)
    ru[n]=up[1:n+1].mean(); rd[n]=dn[1:n+1].mean()
    for i in range(n+1,len(c)): ru[i]=(ru[i-1]*(n-1)+up[i])/n; rd[i]=(rd[i-1]*(n-1)+dn[i])/n
    rs=np.where(rd>0,ru/rd,np.inf); return 100-100/(1+rs)
def _watr(o,h,l,c,n=14):
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1)))); tr[0]=h[0]-l[0]
    atr=np.full_like(c,np.nan)
    if len(c)<=n: return atr
    atr[n]=tr[1:n+1].mean()
    for i in range(n+1,len(c)): atr[i]=(atr[i-1]*(n-1)+tr[i])/n
    return atr
def v4_monthly(pairs=P1_V4_MAJ, risk=0.15):
    from collections import defaultdict
    monthly=defaultdict(float)
    for p in pairs:
        ohlc=daily_ohlc_fx(p)
        if ohlc is None or len(ohlc)<V4_BBwin+V4_HOLD+5: continue
        o=ohlc["o"].values;h=ohlc["h"].values;l=ohlc["l"].values;c=ohlc["c"].values;ts=ohlc.index
        rsi=_wrsi(c,V4_RSI); n=len(c); z=np.full(n,np.nan)
        for i in range(V4_BBwin,n):
            w=c[i-V4_BBwin:i]; mn=w.mean(); s=w.std(ddof=1)
            if s>0: z[i]=(c[i]-mn)/s
        down=np.zeros(n); up=np.zeros(n)
        for i in range(1,n):
            down[i]=down[i-1]+1 if c[i]<c[i-1] else 0; up[i]=up[i-1]+1 if c[i]>c[i-1] else 0
        ret=np.zeros(n); ret[1:]=(c[1:]-c[:-1])/c[:-1]; sig=np.zeros(n)
        for i in range(V4_BBwin,n):
            zlo=(not np.isnan(z[i])) and z[i]<-V4_BBz; zhi=(not np.isnan(z[i])) and z[i]>V4_BBz
            buy=int(rsi[i]<V4_RSIlo)+int(zlo)+int(down[i]>=V4_STREAK)+int(ret[i]<-V4_DAYMOVE)
            sell=int(rsi[i]>V4_RSIhi)+int(zhi)+int(up[i]>=V4_STREAK)+int(ret[i]>V4_DAYMOVE)
            if buy>=4 and buy>sell: sig[i]=1
            elif sell>=4 and sell>buy: sig[i]=-1
        atr=_watr(o,h,l,c,V4_ATR); ps=pip_size(p); half=(2.0*ps)/2.0+0.5*ps; pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn,entry,sl,tp,rpx,bi=pos; ex=None
                if dirn>0:
                    if l[i]-half<=sl: ex=sl
                    elif h[i]-half>=tp: ex=tp
                else:
                    if h[i]+half>=sl: ex=sl
                    elif l[i]+half<=tp: ex=tp
                if ex is None and (i-bi)>=V4_HOLD: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    r=((ex-entry) if dirn>0 else (entry-ex))/rpx; monthly[str(ts[pos[5]])[:7]]+=r*risk; pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    entry=o[i]+(half if s>0 else -half); rpx=atr[i-1]*V4_SLATR
                    sl=entry-rpx if s>0 else entry+rpx; tp=entry+V4_RR*rpx if s>0 else entry-V4_RR*rpx
                    pos=(s,entry,sl,tp,rpx,i)
    s=pd.Series(monthly).sort_index()
    if len(s): s.index=pd.to_datetime(s.index+"-01"); s=s/100.0
    return s
def e5_monthly(assets=P1_E5_BASE, cost_bps=5.0):
    rets,sigs,ws={},{},{}
    for a in assets:
        c=daily_close(a, False)
        if c is None: continue
        m=c.groupby(c.index.to_period("M")).last(); m.index=m.index.to_timestamp()
        if len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB))
        r=m.pct_change(); ws[a]=1.0/r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std()
        rets[a]=r.shift(-1); sigs[a]=pos
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    for t in idx:
        num=den=0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            num+=w*(p0*nx-cost_bps/1e4); den+=w
        if den>0: out[t]=num/den
    return pd.Series(out).sort_index().dropna()

# ---------- 統計/ゲート(canonical と同一) ----------
def perm_p(s,n=4000,seed=13):
    r=pd.Series(s).dropna().values
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def stat(s,ann):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0.0,Sharpe=0.0,maxDD=0.0,Calmar=0.0,n=0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0.0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round(float((eq.iloc[-1]-1)*100),1),Sharpe=round(float(shp),2),maxDD=round(dd,1),
                Calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)))
def jackknife(s):
    s=pd.Series(s).dropna()
    if len(s)==0 or not isinstance(s.index, pd.DatetimeIndex): return None
    yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    return round(max(perm_p(s[s.index.year!=y]) for y in yrs),3)
def walkforward(s,k=5):
    s=pd.Series(s).dropna(); n=len(s); b=[int(n*i/k) for i in range(k+1)]
    return sum(1 for i in range(k) if (1+s.iloc[b[i]:b[i+1]]).prod()-1>0)
def block_bootstrap(s,n_paths=N_PATHS,horizon=None,block=3,seed=SEED):
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,1))
    horizon=horizon or n; rng=np.random.default_rng(seed); P=np.empty((n_paths,horizon))
    for p in range(n_paths):
        seq=[]
        while len(seq)<horizon:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:horizon]
    return P
def p95_maxdd(P):
    mdd=np.zeros(len(P))
    for i in range(len(P)):
        eq=np.cumprod(1+P[i]); peak=np.maximum.accumulate(eq); mdd[i]=((eq-peak)/peak).min()
    return round(float(np.percentile(mdd,5))*100,1)
def score(series, ann, placebo_ok, dd_p95, cost_ok):
    s=pd.Series(series).dropna()
    if len(s)==0 or not isinstance(s.index, pd.DatetimeIndex):
        return dict(grade="LEAD",passed=0,years=0.0,stat=stat(s,ann),perm_p=1.0,bonf=round(BONF,5),jk=None,IS=0.0,OOS=0.0,wf=0,dd_p95=0.0,gates={})
    yrs=(s.index.max()-s.index.min()).days/365.25 if len(s)>1 else 0
    st=stat(s,ann); pp=perm_p(s); jk=jackknife(s)
    h=len(s)//2; IS=(1+s.iloc[:h]).prod()-1; OOS=(1+s.iloc[h:]).prod()-1; wf=walkforward(s)
    G={"G1":yrs>=8.5,"G3":pp<BONF,"G4":bool(placebo_ok),"G5":(jk is not None and jk<=0.10),
       "G6":(IS>0 and OOS>0),"G7":wf>=4,"G8":bool(cost_ok),"G9":dd_p95>=-10.0}
    core=[G["G3"],G["G4"],G["G5"],G["G6"],G["G7"],G["G8"],G["G9"]]
    grade="ADOPT" if all(core) else ("STRONG-LEAD" if (G["G4"] and G["G6"] and G["G7"] and G["G8"]) else "LEAD")
    passed=sum(1 for v in [G["G1"],True]+core if v)
    return dict(grade=grade,passed=passed,years=round(float(yrs),1),stat=st,perm_p=round(pp,4),
                bonf=round(BONF,5),jk=jk,IS=round(float(IS*100),1),OOS=round(float(OOS*100),1),wf=wf,dd_p95=dd_p95,gates=G)
def corr(a,b):
    a=pd.Series(a).dropna(); b=pd.Series(b).dropna(); j=a.index.intersection(b.index)
    if len(j)<12: return None
    return round(float(np.corrcoef(a[j].values,b[j].values)[0,1]),3)

def run():
    print("[準備] Yahoo日足の取得(未配置のみ)…")
    for nm in P1_E5_BASE: fetch_yahoo_daily(nm, False)
    for A,B,fa,fb in PAIRS:
        if fa and _h1_path(A) is None: fetch_yahoo_daily(A,True)
        elif not fa: fetch_yahoo_daily(A,False)
        if fb and _h1_path(B) is None: fetch_yahoo_daily(B,True)
        elif not fb: fetch_yahoo_daily(B,False)
    print("="*80); print("第2ポート C案: リラティブバリュー(統計的ペア) — 同一9ゲート＋現行相関"); print("="*80)
    print(f"事前登録 N={N} (α={BONF:.5f})  RVパラメータ: W_beta={W_BETA} W_z={W_Z} Zentry={Z_ENTRY} Zexit={Z_EXIT} cost={COST_BPS}bps\n")
    sV7=v7_monthly_proxy(); sV4=v4_monthly(); sE5=e5_monthly()

    out={"N":N,"alpha":round(BONF,5),"pairs":{},"survivors":[]}
    for A,B,fa,fb in PAIRS:
        nm=f"{A}/{B}"
        s=rv_monthly(A,B,fa,fb)
        plac=stat(rv_monthly(A,B,fa,fb,randomize=True),12)["net"]; base=stat(s,12)["net"]
        ok=(abs(plac) < abs(base)*0.5) and base>0
        dd=p95_maxdd(block_bootstrap(rv_monthly(A,B,fa,fb,legrisk=RV_LEGRISK),horizon=120,block=3))
        cost=(stat(rv_monthly(A,B,fa,fb,cost_bps=COST_BPS*2),12)["net"]>0)
        r=score(s,12,ok,dd,cost)
        c7=corr(s,sV7); c4=corr(s,sV4); c5=corr(s,sE5)
        cmax=max([abs(x) for x in (c7,c4,c5) if x is not None], default=None)
        r.update(corr_v7=c7,corr_v4=c4,corr_E5=c5,corr_max=cmax)
        out["pairs"][nm]=r
        win=(r["grade"] in ("STRONG-LEAD","ADOPT")) and (cmax is not None and cmax<0.3) and r["dd_p95"]>=-10.0
        if win: out["survivors"].append(nm)
        st_=r["stat"]
        print(f"  {nm:16s}[{r['grade']:11s}]{r['passed']}/9 net{st_['net']:+6.1f}% Sh{st_['Sharpe']:+.2f} DD{st_['maxDD']:+.1f}% | "
              f"perm{r['perm_p']:.3f}<{BONF:.4f}:{r['gates'].get('G3')} G4plac:{r['gates'].get('G4')} JK{r['jk']} "
              f"IS{r['IS']:+.1f}/OOS{r['OOS']:+.1f} WF{r['wf']}/5 p95{r['dd_p95']}% | cmax{cmax}{'  ★候補' if win else ''}")

    print("\n"+"="*80)
    if out["survivors"]:
        print("★合格候補(STRONG-LEAD以上＋対現行相関<0.3＋p95DD≥-10%):", out["survivors"])
        print("→ これを第2ポートのレッグ化(EAは両建てスプレッド)＋合成・デモ前進検証(docs/29)へ。")
    else:
        print("合格候補なし。リラティブバリュー枠でも第2の独立エッジは確認できず。")
        print("→ 残るC候補=キャリー(要金利データ)/ボラ売り(要オプションデータ)は本リポジトリのデータ範囲外。")
        print("  データ範囲内では『並走は実証済みエッジの2口座運用(docs/52 B案)が唯一確実』が最終結論に。")
    print("="*80)
    try:
        path=(DRIVE_BASE+"/portfolioC_relvalue.json") if DRIVE_OK else "research/results/portfolioC_relvalue.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
