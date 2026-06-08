# -*- coding: utf-8 -*-
"""
colab_portfolio2_sweep.py — 第2(並走)ポートフォリオ【規律ある多候補スイープ】。

背景: docs/52 で第2ポートv1(MR=別クロス9本 / RP=銀・原油・FTSE・日経)は不合格(両LEAD・合成枠超過・RP⇄E5=0.43)。
  v4/E5の機構が別ユニバースへ転移しなかった。本スクリプトはユーザー選択「A.規律ある多候補スイープ」に従い、
  **MR/RPの候補ユニバースを複数【事前登録】し、1回のColabで総当り採点**する。

★データスヌープ防止(最重要): 候補を増やすほど"偶然の当たり"が出やすい。そこで **Bonferroni母数Nを
  『プロジェクト継承分 + v1 + 本スイープの全候補数』まで増やす**。後付けで緩めない・数字は盛らない。
    MR: N = 18(v4継承) + 1(v1) + len(MR_SETS)
    RP: N = 6 (E5継承) + 1(v1) + len(RP_SETS)

採点は現行と同一の9ゲート(colab_validate_all_v7standard.py 流用)＋現行(v7/v4maj/E5base)との相関。
合格候補の定義: **判定 STRONG-LEAD以上(G4・G6・G7・G8通過, 欠けはG3/G5のみ) かつ 対応する現行レッグとの相関<0.3
  かつ p95DD ≥ −10%**。1つも無ければ docs/52 §4「データに第2の独立エッジは無い」を更に強固に再確認(誠実な結論)。

使い方(Colab): USE_DRIVE=True。FXクロスはH1(dukascopy)が有れば優先、無ければYahoo日足を自動取得。
  指数/先物/暗号はYahoo日足を自動取得。「すべて実行」。
⚠ シミュレーション(Yahoo=配当/限月/実スワップ未精緻・先物は連結近月)。将来/ライブ約定を保証しない。確証はデモ(docs/29)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

# ===== MR候補(平均回帰・v4機構・全てFX・現行v4の9メジャーと非重複) =====
# 診断(docs/52): v1はトレンド性クロス混入で空振り→レンジ性を優先して再選定。
MR_SETS = {
  "MR-A_range":   ["EURGBP","EURCHF","AUDNZD","NZDCAD","AUDCAD"],     # 最もレンジ性が高いクロス
  "MR-B_jpyx":    ["CADJPY","AUDJPY","NZDJPY","CHFJPY"],              # v4が持たないJPYクロス
  "MR-C_eurgbpx": ["EURGBP","EURCHF","GBPCHF","EURNZD","GBPNZD"],     # EUR/GBPクロス
}
# ===== RP候補(トレンド追随・E5機構・現行E5の金+米独指数と非重複) =====
# 診断(docs/52): 銀/原油/FTSEは非トレンドで負。トレンド持続 or 非株の分散源を優先。
RP_SETS = {
  "RP-A_rates":   ["UST10","UST30","UST5"],                          # 米国債先物=非株・金利トレンド
  "RP-B_macro":   ["DXY","UST10","COPPER","NATGAS"],                 # ドル指数/債券/銅/天然ガス=クロスアセット
  "RP-C_asiaeu":  ["JP225","HK50","AUS200","FRA40"],                 # 非米独の株指数(株相関は要検証)
  "RP-D_crypto":  ["BTCUSD","ETHUSD","COPPER","NATGAS"],             # 暗号+コモディティ=強トレンド(beta/placebo要検証)
}
# 現行(相関比較対象)
P1_V7_YEN   = ["EURJPY","GBPJPY","USDJPY"]
P1_V4_MAJ   = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
P1_E5_BASE  = ["XAUUSD","US500","NAS100","GER40"]

# Yahoo シンボル対応(自動取得)
_YH = {
  # 代替バスケット/相関用
  "XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI",
  "UST10":"ZN=F","UST30":"ZB=F","UST5":"ZF=F","DXY":"DX=F","COPPER":"HG=F","NATGAS":"NG=F",
  "JP225":"^N225","HK50":"^HSI","AUS200":"^AXJO","FRA40":"^FCHI","UK100":"^FTSE","EU50":"^STOXX50E",
  "BTCUSD":"BTC-USD","ETHUSD":"ETH-USD","XAGUSD":"SI=F","USOIL":"CL=F",
}
def yahoo_of(name, fx):
    if name in _YH: return _YH[name]
    if fx and len(name)==6 and name.isalpha(): return name+"=X"
    return None

HOURS   = [4,6,8,10]
LB      = [1,3,6,12]; VOLWIN=12
COST_PIP= 2.0
N_MR = 18 + 1 + len(MR_SETS)     # =22 → α≈0.00227 (v4継承18 + v1 + 本スイープ)
N_RP = 6  + 1 + len(RP_SETS)     # =11 → α≈0.00455 (E5継承6  + v1 + 本スイープ)
MR_RISK_PER_TRADE=0.15; RP_LEGRISK=0.30
V4_RSI=14; V4_RSIlo=35.0; V4_RSIhi=65.0; V4_BBwin=20; V4_BBz=1.5; V4_STREAK=3
V4_DAYMOVE=0.005; V4_ATR=14; V4_SLATR=1.5; V4_RR=1.2; V4_HOLD=8
N_PATHS=4000; SEED=11

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")

def pip_size(p): return 0.01 if (len(p)>=6 and p.endswith("JPY")) else 0.0001

# ---------- データ取得/読込(fxフラグで明示) ----------
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
    """Yahoo日足OHLCを DAILY_DIR/{name}_d.csv に保存。"""
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
def daily_ohlc(name, fx):
    """日足OHLC。FXはH1(dukascopy)優先→無ければYahoo日足。非FXはYahoo日足。"""
    key=("ohlc",name)
    if key in CACHE: return CACHE[key]
    df=None
    if fx:
        p=_h1_path(name)
        if p is not None:
            d=_read(p); o=_col(d,"open","bidopen","o"); h=_col(d,"high","bidhigh","h")
            l=_col(d,"low","bidlow","l"); c=_col(d,"close","bidclose","c")
            if c is not None:
                ohlc=pd.DataFrame({"o":o if o is not None else c,"h":h if h is not None else c,
                                   "l":l if l is not None else c,"c":c})
                df=ohlc.resample("1D").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    if df is None:
        if _daily_path(name) is None: fetch_yahoo_daily(name, fx)
        p=_daily_path(name)
        if p is not None:
            d=_read(p); o=_col(d,"open","o"); h=_col(d,"high","h"); l=_col(d,"low","l"); c=_col(d,"close","c")
            if c is not None:
                df=pd.DataFrame({"o":o if o is not None else c,"h":h if h is not None else c,
                                 "l":l if l is not None else c,"c":c}).dropna()
    CACHE[key]=df; return df
def daily_close(name, fx):
    o=daily_ohlc(name, fx)
    return None if o is None else o["c"]
def monthly_close(name, fx):
    c=daily_close(name, fx)
    if c is None: return None
    m=c.groupby(c.index.to_period("M")).last(); m.index=m.index.to_timestamp(); return m

# ---------- MR(v4機構) ----------
def _wilder_rsi(c, n=14):
    d=np.diff(c, prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    ru=np.full_like(c,np.nan); rd=np.full_like(c,np.nan)
    if len(c)<=n: return np.full_like(c,50.0)
    ru[n]=up[1:n+1].mean(); rd[n]=dn[1:n+1].mean()
    for i in range(n+1,len(c)):
        ru[i]=(ru[i-1]*(n-1)+up[i])/n; rd[i]=(rd[i-1]*(n-1)+dn[i])/n
    rs=np.where(rd>0, ru/rd, np.inf); return 100-100/(1+rs)
def _wilder_atr(o,h,l,c,n=14):
    tr=np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1)))); tr[0]=h[0]-l[0]
    atr=np.full_like(c,np.nan)
    if len(c)<=n: return atr
    atr[n]=tr[1:n+1].mean()
    for i in range(n+1,len(c)): atr[i]=(atr[i-1]*(n-1)+tr[i])/n
    return atr
def _v4_signals(c, randomize=False, rng=None):
    rsi=_wilder_rsi(c,V4_RSI); n=len(c); z=np.full(n,np.nan)
    for i in range(V4_BBwin,n):
        w=c[i-V4_BBwin:i]; m=w.mean(); s=w.std(ddof=1)
        if s>0: z[i]=(c[i]-m)/s
    down=np.zeros(n); up=np.zeros(n)
    for i in range(1,n):
        down[i]=down[i-1]+1 if c[i]<c[i-1] else 0
        up[i]=up[i-1]+1 if c[i]>c[i-1] else 0
    ret=np.zeros(n); ret[1:]=(c[1:]-c[:-1])/c[:-1]; sig=np.zeros(n)
    for i in range(V4_BBwin,n):
        zlo=(not np.isnan(z[i])) and z[i]<-V4_BBz; zhi=(not np.isnan(z[i])) and z[i]>V4_BBz
        buy =int(rsi[i]<V4_RSIlo)+int(zlo)+int(down[i]>=V4_STREAK)+int(ret[i]<-V4_DAYMOVE)
        sell=int(rsi[i]>V4_RSIhi)+int(zhi)+int(up[i]>=V4_STREAK)+int(ret[i]> V4_DAYMOVE)
        if buy>=4 and buy>sell: sig[i]=1
        elif sell>=4 and sell>buy: sig[i]=-1
    if randomize and rng is not None:
        idx=np.where(sig!=0)[0]; out=np.zeros(n); out[idx]=rng.choice([-1,1], size=len(idx)); return out
    return sig
def mr_monthly(pairs, cost_mult=1.0, randomize=False, seed=7, risk=MR_RISK_PER_TRADE, fx=True):
    from collections import defaultdict
    rng=np.random.default_rng(seed); monthly=defaultdict(float)
    for p in pairs:
        ohlc=daily_ohlc(p, fx)
        if ohlc is None or len(ohlc)<V4_BBwin+V4_HOLD+5: continue
        ts=ohlc.index; o=ohlc["o"].values; h=ohlc["h"].values; l=ohlc["l"].values; c=ohlc["c"].values
        sig=_v4_signals(c, randomize=randomize, rng=rng)
        atr=_wilder_atr(o,h,l,c,V4_ATR); ps=pip_size(p)
        half=(2.0*ps)/2.0*cost_mult + 0.5*ps*cost_mult
        pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn,entry,sl,tp,risk_px,bi=pos; ex=None
                if dirn>0:
                    if l[i]-half<=sl: ex=sl
                    elif h[i]-half>=tp: ex=tp
                else:
                    if h[i]+half>=sl: ex=sl
                    elif l[i]+half<=tp: ex=tp
                if ex is None and (i-bi)>=V4_HOLD: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    r=((ex-entry) if dirn>0 else (entry-ex))/risk_px
                    monthly[str(ts[pos[5]])[:7]]+=r*risk; pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    entry=o[i]+(half if s>0 else -half); risk_px=atr[i-1]*V4_SLATR
                    sl=entry-risk_px if s>0 else entry+risk_px
                    tp=entry+V4_RR*risk_px if s>0 else entry-V4_RR*risk_px
                    pos=(s,entry,sl,tp,risk_px,i)
    s=pd.Series(monthly).sort_index()
    if len(s)==0: return s
    s.index=pd.to_datetime(s.index+"-01"); return s/100.0

# ---------- RP(E5機構) ----------
def rp_monthly(assets, cost_bps=5.0, randomize=False, seed=7, legrisk=None, fx=False):
    rng=np.random.default_rng(seed); rets,sigs,ws={},{},{}
    for a in assets:
        m=monthly_close(a, fx)
        if m is None or len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB))
        r=m.pct_change(); ws[a]=1.0/r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std()
        rets[a]=r.shift(-1); sigs[a]=pos
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    cmul={"NATGAS":2.0,"BTCUSD":2.0,"ETHUSD":2.0,"USOIL":1.5}   # 高コスト資産は割増
    for t in idx:
        num=den=0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            cb=cost_bps*cmul.get(a,1.0)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            dirn=rng.choice([-1,1]) if randomize else p0
            num+=w*(dirn*nx-cb/1e4); den+=w
        if den>0: out[t]=num/den
    s=pd.Series(out).sort_index().dropna()
    if legrisk is not None and s.std()>0:
        s=s/s.std()*(legrisk/100.0*np.sqrt(max(len(assets),1)))
    return s

# ---------- 現行系列(相関用) ----------
def v7_monthly_proxy():
    from collections import defaultdict
    monthly=defaultdict(float)
    for p in P1_V7_YEN:
        ohlc=daily_ohlc(p, True)   # 日足近似(相関用途には十分)
        # 月曜LONGの日次近似が必要なのでH1終値を使う方が正確: ここでは日足の曜日で近似
    # より正確なv7プロキシ(H1)があれば使う
    for p in P1_V7_YEN:
        ph=_h1_path(p)
        if ph is None: continue
        d=_read(ph); c=_col(d,"close","bidclose","c")
        if c is None: continue
        cv=c.values; idx=c.index; ps=pip_size(p)
        for h in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==h))[0]; a=a[a+24<len(cv)]
            for k in a: monthly[str(idx[k])[:7]]+=(cv[k+24]-cv[k])/cv[k]-COST_PIP*ps/cv[k]
    s=pd.Series(monthly).sort_index()
    if len(s): s.index=pd.to_datetime(s.index+"-01")
    return s

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
def score(series, ann, N, placebo_ok, dd_p95, cost_ok):
    s=pd.Series(series).dropna()
    if len(s)==0 or not isinstance(s.index, pd.DatetimeIndex):
        return dict(grade="LEAD", passed=0, years=0.0, stat=stat(s,ann), perm_p=1.0,
                    bonf=round(0.05/N,5), jk=None, IS=0.0, OOS=0.0, wf=0, dd_p95=0.0, gates={})
    yrs=(s.index.max()-s.index.min()).days/365.25 if len(s)>1 else 0
    st=stat(s,ann); pp=perm_p(s); bonf=0.05/N; jk=jackknife(s)
    h=len(s)//2; IS=(1+s.iloc[:h]).prod()-1; OOS=(1+s.iloc[h:]).prod()-1; wf=walkforward(s)
    G={"G1":yrs>=8.5,"G3":pp<bonf,"G4":bool(placebo_ok),"G5":(jk is not None and jk<=0.10),
       "G6":(IS>0 and OOS>0),"G7":wf>=4,"G8":bool(cost_ok),"G9":dd_p95>=-10.0}
    core=[G["G3"],G["G4"],G["G5"],G["G6"],G["G7"],G["G8"],G["G9"]]
    if all(core): grade="ADOPT"
    elif G["G4"] and G["G6"] and G["G7"] and G["G8"]: grade="STRONG-LEAD"
    else: grade="LEAD"
    passed=sum(1 for v in [G["G1"],True]+core if v)
    return dict(grade=grade, passed=passed, years=round(float(yrs),1), stat=st, perm_p=round(pp,4),
                bonf=round(bonf,5), jk=jk, IS=round(float(IS*100),1), OOS=round(float(OOS*100),1),
                wf=wf, dd_p95=dd_p95, gates=G)
def corr(a,b):
    a=pd.Series(a).dropna(); b=pd.Series(b).dropna(); j=a.index.intersection(b.index)
    if len(j)<12: return None
    return round(float(np.corrcoef(a[j].values,b[j].values)[0,1]),3)

def run():
    # 取得が要る非FX/FXを先に確保
    print("[準備] Yahoo日足の取得(未配置のみ)…")
    for nm in P1_E5_BASE: fetch_yahoo_daily(nm, False)
    for st in RP_SETS.values():
        for a in st: fetch_yahoo_daily(a, False)
    for st in MR_SETS.values():
        for a in st:
            if _h1_path(a) is None: fetch_yahoo_daily(a, True)
    print("="*78); print("第2(並走)ポートフォリオ 多候補スイープ — 同一9ゲート＋現行相関(Bonferroni N増)"); print("="*78)
    print(f"事前登録 N: MR={N_MR}(α={0.05/N_MR:.5f})  RP={N_RP}(α={0.05/N_RP:.5f})  ※候補数で増・後付け緩和なし\n")

    # 現行(相関基準)
    sV7=v7_monthly_proxy(); sV4maj=mr_monthly(P1_V4_MAJ, fx=True); sE5base=rp_monthly(P1_E5_BASE, fx=False)
    out={"N":{"MR":N_MR,"RP":N_RP},"MR":{},"RP":{},"survivors":[]}

    print("───── MR候補(平均回帰・v4機構・FXクロス) ─────")
    for name,uni in MR_SETS.items():
        s=mr_monthly(uni, fx=True)
        plac=stat(mr_monthly(uni, randomize=True, fx=True),12)["net"]; ok=(plac < stat(s,12)["net"]*0.5)
        dd=p95_maxdd(block_bootstrap(mr_monthly(uni, fx=True),horizon=120,block=3))
        cost=(stat(mr_monthly(uni, cost_mult=2.0, fx=True),12)["net"]>0)
        r=score(s,12,N_MR,ok,dd,cost)
        cv4=corr(s,sV4maj); cv7=corr(s,sV7)
        r.update(corr_v4=cv4, corr_v7=cv7, universe=uni)
        out["MR"][name]=r
        win=(r["grade"] in ("STRONG-LEAD","ADOPT")) and (cv4 is not None and abs(cv4)<0.3) and r["dd_p95"]>=-10.0
        if win: out["survivors"].append(("MR",name))
        st_=r["stat"]
        print(f"  {name:13s} [{r['grade']:11s}] {r['passed']}/9  net{st_['net']:+6.1f}% Sh{st_['Sharpe']:+.2f} "
              f"DD{st_['maxDD']:+.1f}% | perm{r['perm_p']:.3f}<{r['bonf']:.4f}:{r['gates'].get('G3')} "
              f"JK{r['jk']} IS{r['IS']:+.1f}/OOS{r['OOS']:+.1f} WF{r['wf']}/5 p95{r['dd_p95']}% | "
              f"corr_v4={cv4} corr_v7={cv7}{'  ★候補' if win else ''}")

    print("\n───── RP候補(トレンド追随・E5機構) ─────")
    for name,uni in RP_SETS.items():
        s=rp_monthly(uni, fx=False)
        plac=stat(rp_monthly(uni, randomize=True, fx=False),12)["net"]; ok=(plac < stat(s,12)["net"]*0.5)
        sacc=rp_monthly(uni, legrisk=RP_LEGRISK, fx=False)
        dd=p95_maxdd(block_bootstrap(sacc,horizon=120,block=3))
        cost=(stat(rp_monthly(uni, cost_bps=10.0, fx=False),12)["net"]>0)
        r=score(s,12,N_RP,ok,dd,cost)
        ce5=corr(s,sE5base); cv7=corr(s,sV7)
        r.update(corr_E5=ce5, corr_v7=cv7, universe=uni)
        out["RP"][name]=r
        win=(r["grade"] in ("STRONG-LEAD","ADOPT")) and (ce5 is not None and abs(ce5)<0.3) and r["dd_p95"]>=-10.0
        if win: out["survivors"].append(("RP",name))
        st_=r["stat"]
        print(f"  {name:13s} [{r['grade']:11s}] {r['passed']}/9  net{st_['net']:+6.1f}% Sh{st_['Sharpe']:+.2f} "
              f"DD{st_['maxDD']:+.1f}% | perm{r['perm_p']:.3f}<{r['bonf']:.4f}:{r['gates'].get('G3')} "
              f"JK{r['jk']} IS{r['IS']:+.1f}/OOS{r['OOS']:+.1f} WF{r['wf']}/5 p95{r['dd_p95']}% | "
              f"corr_E5={ce5} corr_v7={cv7}{'  ★候補' if win else ''}")

    print("\n"+"="*78)
    if out["survivors"]:
        print("★合格候補(STRONG-LEAD以上 ＋ 対現行相関<0.3 ＋ p95DD≥-10%):")
        for leg,nm in out["survivors"]:
            u=out[leg][nm]["universe"]; print(f"   {leg} {nm}: {u}")
        print("→ MR候補×RP候補で合成し、現行との相関・合成p95DDを再確認(本スクリプトの合成部を流用)してから")
        print("  デモ前進検証(docs/29)。次の一手は『候補の組合せで第2ポートを再構築』。")
    else:
        print("合格候補なし。docs/52 §4『この相場データに第2の独立エッジは無い』を更に強固に再確認。")
        print("→ 現実的には docs/52 §5 B(実証済みエッジを2口座へ)が確実。A継続(更なる候補)は期待逓減。")
    print("="*78)
    try:
        path=(DRIVE_BASE+"/portfolio2_sweep.json") if DRIVE_OK else "research/results/portfolio2_sweep.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
