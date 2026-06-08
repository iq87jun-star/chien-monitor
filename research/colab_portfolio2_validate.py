# -*- coding: utf-8 -*-
"""
colab_portfolio2_validate.py — 第2(並走)ポートフォリオを【現行と同一の v7基準9ゲート】で採点し、
                               かつ現行ポートフォリオ(v7+v4+E5)との相関を測る。

目的(ユーザー要望): 「現行ポートフォリオとは別に、同じレベルの検証を通った並走ポートフォリオを作る」。
方針(ユーザー選択=既存エッジ再構成型): 検証済みの【機構】を、現行が触らない【別ユニバース】へ展開する。
  - Leg-A  MR(v4機構=日足k≥4合議の平均回帰) を【現行v4が使わないクロス9本】へ。
  - Leg-B  RP(E5機構=月次リスクパリティTSMOM) を【現行E5が使わない資産バスケット】へ。
  v7(円月曜)は意図的に複製しない —— 同じ取引を2口座で重ねると相関してしまい「並走」の意味が消えるため。
  → 2口座が同じトレードを一切共有しない=真に並走できる第2ポートフォリオ。

検証は現行と全く同じ。各レッグを下記9ゲートで採点し、合成系列と現行各レッグの相関も出す。数字は盛らない。

v7基準ゲート(9):
  G1 10年実データ(span≈10y)              G6 IS/OOS 両方+ (減衰なし)
  G2 ノールックアヘッド+実コスト(構造)    G7 ウォークフォワード ≥4/5期 +
  G3 主signのperm_p < Bonferroni α        G8 コスト頑健(2×コストでも net>0)
  G4 プラセボ識別(MR=方向, RP=方向)       G9 −10%枠に収まる(p95 maxDD ≥ −10%)
  G5 年次ジャックナイフ max_p ≤ 0.10

判定(colab_validate_all_v7standard.py と同一ロジック):
  ADOPT       = G3・G4・G5・G6・G7・G8・G9 すべて合格
  STRONG-LEAD = G4・G6・G7・G8 合格だが G3(Bonf)か G5 のみ未達(質は高いが確証のみ不足→デモで埋める)
  LEAD        = それ未満

事前登録 Bonferroni 母数 N(後付けで緩めない):
  MR-crosses : v4 と同一機構・同一固定パラメータ(探索なし)を別ユニバースへ1回適用。
               規律上、v4の事前登録 N=18 を継承(α=0.05/18≈0.00278・保守)。
  RP-altbskt : E5 と同一機構を別バスケットへ1回適用。E5の事前登録 N=6 を継承(α=0.05/6≈0.00833)。

使い方(Colab): USE_DRIVE=True。
  H1_DIR  に クロスH1(10年): EURGBP,EURAUD,EURCHF,EURCAD,GBPAUD,AUDCAD,AUDNZD,GBPCHF,CADJPY の _h1.csv
            ＋(相関用)現行v4の9メジャー・現行v7の円3クロス
  DAILY_DIR に 代替バスケット日足(10年): XAGUSD,USOIL,UK100,JP225 (無ければYahoo自動取得)
            ＋(相関用)現行E5の XAUUSD,US500,NAS100,GER40
  「すべて実行」。最終判定はデモ前進検証(docs/29)で確証する点も現行と同じ。
⚠ シミュレーション。指数/コモディティ=配当・限月・実スワップ未精緻。将来/ライブ約定を保証しない。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

# ===== 第2ポートフォリオの別ユニバース(現行と非重複) =====
MR_CROSSES  = ["EURGBP","EURAUD","EURCHF","EURCAD","GBPAUD","AUDCAD","AUDNZD","GBPCHF","CADJPY"]
RP_ALTBASKET= ["XAGUSD","USOIL","UK100","JP225"]   # 銀 / WTI原油 / 英FTSE / 日経225
# ===== 現行ポートフォリオ(相関の比較対象) =====
P1_V7_YEN   = ["EURJPY","GBPJPY","USDJPY"]
P1_V4_MAJ   = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
P1_E5_BASE  = ["XAUUSD","US500","NAS100","GER40"]

HOURS   = [4,6,8,10]
LB      = [1,3,6,12]; VOLWIN=12
COST_PIP= 2.0
BONF_N  = {"MR":18, "RP":6}        # 事前登録(v4/E5を継承・後付けで緩めない)
MR_RISK_PER_TRADE=0.15             # 代表デプロイ・サイズ(G9評価用, %/トレード)
RP_LEGRISK=0.30                    # 代表デプロイ・サイズ(G9評価用, legRisk%)
# v4機構の固定パラメータ(現行と同一)
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

def is_fx(name): return len(name)==6 and name.isalpha()
def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(name, daily=False):
    if daily: c=[f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:     c=[f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None
def _load_close(name, daily):
    path=_resolve(name, daily=daily)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()
def _load_ohlc(name, daily):
    """日足OHLC(MRシミュレータ用)。FXはH1→日足にリサンプル、その他は日足CSV。"""
    path=_resolve(name, daily=daily)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*names):
        for n in names:
            if n in df.columns: return df[n].astype(float)
        return None
    o=col("open","bidopen","o"); h=col("high","bidhigh","h"); l=col("low","bidlow","l"); c=col("close","bidclose","c")
    if c is None: return None
    if o is None: o=c
    if h is None: h=c
    if l is None: l=c
    ohlc=pd.DataFrame({"o":o,"h":h,"l":l,"c":c})
    if not daily:   # FX H1 → 日足
        ohlc=ohlc.resample("1D").agg({"o":"first","h":"max","l":"min","c":"last"}).dropna()
    return ohlc

CACHE={}
def H1C(p):
    if ("h",p) not in CACHE: CACHE[("h",p)]=_load_close(p, False)
    return CACHE[("h",p)]
def DC(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_load_close(n, True)
    return CACHE[("d",n)]
def DAILY_OHLC(name):
    key=("ohlc",name)
    if key not in CACHE: CACHE[key]=_load_ohlc(name, daily=not is_fx(name))
    return CACHE[key]

# ----- Yahoo フォールバック(代替バスケット日足 / クロス日足) -----
_YH={"XAGUSD":"SI=F","USOIL":"CL=F","UK100":"^FTSE","JP225":"^N225",
     "XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_daily(names):
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out_dir,exist_ok=True)
    for name in names:
        if _resolve(name,daily=True) is not None: continue
        yh=_YH.get(name) or (f"{name}=X" if is_fx(name) else None)
        if yh is None: continue
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
            CACHE.pop(("d",name),None); CACHE.pop(("ohlc",name),None); print(f"  [取得] {name}"); time.sleep(1.0)
        except Exception as e: print(f"  [取得失敗] {name}: {str(e)[:40]}")

# ================= MR レッグ(v4機構=日足k≥4合議・別クロス) =================
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
    rsi=_wilder_rsi(c,V4_RSI); n=len(c)
    z=np.full(n,np.nan)
    for i in range(V4_BBwin,n):
        w=c[i-V4_BBwin:i]; m=w.mean(); s=w.std(ddof=1)
        if s>0: z[i]=(c[i]-m)/s
    down=np.zeros(n); up=np.zeros(n)
    for i in range(1,n):
        down[i]=down[i-1]+1 if c[i]<c[i-1] else 0
        up[i]=up[i-1]+1 if c[i]>c[i-1] else 0
    ret=np.zeros(n); ret[1:]=(c[1:]-c[:-1])/c[:-1]
    sig=np.zeros(n)
    for i in range(V4_BBwin,n):
        zlo=(not np.isnan(z[i])) and z[i]<-V4_BBz; zhi=(not np.isnan(z[i])) and z[i]>V4_BBz
        buy =int(rsi[i]<V4_RSIlo)+int(zlo)+int(down[i]>=V4_STREAK)+int(ret[i]<-V4_DAYMOVE)
        sell=int(rsi[i]>V4_RSIhi)+int(zhi)+int(up[i]>=V4_STREAK)+int(ret[i]> V4_DAYMOVE)
        if buy>=4 and buy>sell: sig[i]=1
        elif sell>=4 and sell>buy: sig[i]=-1
    if randomize and rng is not None:    # 整合プラセボ=同機会・ランダム方向
        idx=np.where(sig!=0)[0]; out=np.zeros(n)
        out[idx]=rng.choice([-1,1], size=len(idx)); return out
    return sig

def mr_monthly(pairs=MR_CROSSES, cost_mult=1.0, randomize=False, seed=7, risk=MR_RISK_PER_TRADE):
    """k≥4合議トレード(SL=1.5ATR/RR1.2/8日)の口座%P&Lを、エントリー月で集計(全クロス合算)。"""
    from collections import defaultdict
    rng=np.random.default_rng(seed); monthly=defaultdict(float)
    for p in pairs:
        ohlc=DAILY_OHLC(p)
        if ohlc is None or len(ohlc)<V4_BBwin+V4_HOLD+5: continue
        ts=ohlc.index; o=ohlc["o"].values; h=ohlc["h"].values; l=ohlc["l"].values; c=ohlc["c"].values
        sig=_v4_signals(c, randomize=randomize, rng=rng)
        atr=_wilder_atr(o,h,l,c,V4_ATR); ps=pip_size(p)
        half=(2.0*ps)/2.0*cost_mult + 0.5*ps*cost_mult   # spread/2+slippage 概算(クロスは2pip相当)
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
    s.index=pd.to_datetime(s.index+"-01"); return s/100.0   # risk は%表記→分数

# ================= RP レッグ(E5機構=月次リスクパリティ・別バスケット) =================
def rp_monthly(assets=RP_ALTBASKET, cost_bps=5.0, randomize=False, seed=7, legrisk=None):
    rng=np.random.default_rng(seed); rets,sigs,ws={},{},{}
    for a in assets:
        d=DC(a)
        if d is None: continue
        m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp()
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
            cb=cost_bps*(1.5 if a=="USOIL" else 1.0)    # 原油はコスト割増
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            dirn=rng.choice([-1,1]) if randomize else p0
            num+=w*(dirn*nx-cb/1e4); den+=w
        if den>0: out[t]=num/den
    s=pd.Series(out).sort_index().dropna()
    if legrisk is not None and s.std()>0:      # 代表legRiskへスケール(G9用)
        s=s/s.std()*(legrisk/100.0*np.sqrt(len(assets)))
    return s

# ================= 現行ポートフォリオ系列(相関用) =================
def v7_monthly_proxy():
    from collections import defaultdict
    monthly=defaultdict(float)
    for p in P1_V7_YEN:
        s=H1C(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for h in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==h))[0]; a=a[a+24<len(cv)]
            for k in a: monthly[str(idx[k])[:7]]+=(cv[k+24]-cv[k])/cv[k]-COST_PIP*ps/cv[k]
    s=pd.Series(monthly).sort_index()
    if len(s): s.index=pd.to_datetime(s.index+"-01")
    return s

# ================= 統計(canonical と同一) =================
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
    horizon=horizon or n
    rng=np.random.default_rng(seed); P=np.empty((n_paths,horizon))
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

# ================= 9ゲート採点 =================
def grade(name, series, ann, placebo_ok, placebo_desc, dd_p95, dd_size_desc, cost_ok):
    s=pd.Series(series).dropna()
    if len(s)==0 or not isinstance(s.index, pd.DatetimeIndex):
        G={k:False for k in ("G1_10y","G3_perm_bonf","G4_placebo","G5_jackknife",
            "G6_IS_OOS","G7_walkforward","G8_cost","G9_DDfit")}; G["G2_nolook_cost"]=True
        return dict(stat=stat(s,ann), perm_p=1.0, bonf_alpha=round(0.05/BONF_N[name],5),
                    jackknife_max=None, IS_pct=0.0, OOS_pct=0.0, wf="0/5", years=0.0,
                    placebo="(データ無し=未取得)", dd_p95=0.0, dd_size=dd_size_desc, gates=G)
    yrs=(s.index.max()-s.index.min()).days/365.25 if len(s)>1 else 0
    st=stat(s,ann); pp=perm_p(s); bonf=0.05/BONF_N[name]
    jk=jackknife(s); h=len(s)//2; IS=(1+s.iloc[:h]).prod()-1; OOS=(1+s.iloc[h:]).prod()-1
    wf=walkforward(s)
    G={}
    G["G1_10y"]=yrs>=8.5
    G["G2_nolook_cost"]=True
    G["G3_perm_bonf"]=(pp<bonf)
    G["G4_placebo"]=bool(placebo_ok)
    G["G5_jackknife"]=(jk is not None and jk<=0.10)
    G["G6_IS_OOS"]=(IS>0 and OOS>0)
    G["G7_walkforward"]=(wf>=4)
    G["G8_cost"]=bool(cost_ok)
    G["G9_DDfit"]=(dd_p95>=-10.0)
    return dict(stat=st, perm_p=round(pp,4), bonf_alpha=round(bonf,5), jackknife_max=jk,
                IS_pct=round(float(IS*100),1), OOS_pct=round(float(OOS*100),1), wf=f"{wf}/5",
                years=round(float(yrs),1), placebo=placebo_desc, dd_p95=dd_p95, dd_size=dd_size_desc, gates=G)
def finalize_grade(G):
    core=[G["G3_perm_bonf"],G["G4_placebo"],G["G5_jackknife"],G["G6_IS_OOS"],
          G["G7_walkforward"],G["G8_cost"],G["G9_DDfit"]]
    if all(core): return "ADOPT"
    if G["G4_placebo"] and G["G6_IS_OOS"] and G["G7_walkforward"] and G["G8_cost"]:
        return "STRONG-LEAD"
    return "LEAD"

def corr(a,b):
    a=pd.Series(a).dropna(); b=pd.Series(b).dropna()
    j=a.index.intersection(b.index)
    if len(j)<12: return None, len(j)
    return round(float(np.corrcoef(a[j].values,b[j].values)[0,1]),3), len(j)

def run():
    need_daily=[a for a in RP_ALTBASKET+P1_E5_BASE if _resolve(a,daily=True) is None]
    if need_daily:
        print("[診断] 日足未配置→Yahoo取得:", need_daily); ensure_daily(need_daily)
    print("="*74); print("第2(並走)ポートフォリオ — 現行と同一9ゲートで採点 ＋ 現行との相関"); print("="*74)
    out={}

    # ---- Leg-A: MR(別クロス) ----
    sMR=mr_monthly()
    placMR=stat(mr_monthly(randomize=True),12)["net"]; okMR=(placMR < stat(sMR,12)["net"]*0.5)
    ddMR=p95_maxdd(block_bootstrap(mr_monthly(risk=MR_RISK_PER_TRADE),horizon=120,block=3))
    costMR=(stat(mr_monthly(cost_mult=2.0),12)["net"]>0)
    rMR=grade("MR", sMR, 12, okMR, f"方向プラセボnet{placMR}%(本物の半分未満で価値)", ddMR, f"risk/trade{MR_RISK_PER_TRADE}%", costMR)
    rMR["grade"]=finalize_grade(rMR["gates"]); out["MR_crosses"]=rMR

    # ---- Leg-B: RP(別バスケット) ----
    sRP=rp_monthly()
    placRP=stat(rp_monthly(randomize=True),12)["net"]; okRP=(placRP < stat(sRP,12)["net"]*0.5)
    rp_acct=rp_monthly(legrisk=RP_LEGRISK)
    ddRP=p95_maxdd(block_bootstrap(rp_acct,horizon=120,block=3))
    costRP=(stat(rp_monthly(cost_bps=10.0),12)["net"]>0)
    rRP=grade("RP", sRP, 12, okRP, f"方向プラセボnet{placRP}%(本物の半分未満で価値)", ddRP, f"legRisk{RP_LEGRISK}%", costRP)
    rRP["grade"]=finalize_grade(rRP["gates"]); out["RP_altbasket"]=rRP

    for nm,r in (("MR_crosses",rMR),("RP_altbasket",rRP)):
        g=r["gates"]; st=r["stat"]; passed=sum(1 for v in g.values() if v is True)
        print(f"\n■ {nm}  [{r['grade']}]  ({passed}/9)")
        print(f"   span{r['years']}y net{st['net']}% Sharpe{st['Sharpe']} maxDD{st['maxDD']}% Calmar{st['Calmar']} n={st['n']}")
        print(f"   G3_perm{r['perm_p']}<bonf{r['bonf_alpha']}:{g['G3_perm_bonf']}  G4_plac:{g['G4_placebo']}  "
              f"G5_JK({r['jackknife_max']}≤0.10):{g['G5_jackknife']}  G6_IS/OOS({r['IS_pct']}/{r['OOS_pct']}):{g['G6_IS_OOS']}")
        print(f"   G7_WF{r['wf']}:{g['G7_walkforward']}  G8_cost2x:{g['G8_cost']}  G9_DDfit(p95{r['dd_p95']}%@{r['dd_size']}):{g['G9_DDfit']}")

    # ---- 第2ポートフォリオ合成(MR:RP=50:50 リスク等配・正規化合算) ----
    def norm(s): s=pd.Series(s).dropna(); return s/s.std() if s.std()>0 else s
    j=norm(sMR).index.intersection(norm(sRP).index)
    p2=(norm(sMR).reindex(j).fillna(0)*0.5 + norm(sRP).reindex(j).fillna(0)*0.5)
    p2=p2/ (p2.std() if p2.std()>0 else 1) * (RP_LEGRISK/100.0*2)   # 代表サイズへ
    st2=stat(p2,12); dd2=p95_maxdd(block_bootstrap(p2,horizon=120,block=3))
    print(f"\n■ 第2ポートフォリオ合成(MR:RP=50:50)  net{st2['net']}% Sharpe{st2['Sharpe']} maxDD{st2['maxDD']}% p95DD{dd2}%")

    # ---- 現行(v7/v4/E5)との相関 = 並走可否の核心 ----
    sV7=v7_monthly_proxy(); sV4maj=mr_monthly(pairs=P1_V4_MAJ); sE5base=rp_monthly(assets=P1_E5_BASE)
    print("\n--- 現行ポートフォリオとの月次相関(低いほど真の並走) ---")
    cmatrix={}
    for an,a in (("P2_MRcross",sMR),("P2_RPalt",sRP),("P2_combo",p2)):
        row={}
        for bn,b in (("P1_v7",sV7),("P1_v4maj",sV4maj),("P1_E5base",sE5base)):
            cc,nm=corr(a,b); row[bn]=cc
            print(f"   corr({an} , {bn}) = {cc}  (共通{nm}ヶ月)")
        cmatrix[an]=row
    # レッグ内相関(MR⇄RP)
    cMRRP,nMRRP=corr(sMR,sRP); print(f"   corr(P2_MRcross , P2_RPalt) = {cMRRP}  (内部分散, 共通{nMRRP}ヶ月)")

    out["portfolio2"]={"weights":"MR:RP=50:50","stat":st2,"p95DD":dd2}
    out["correlation_vs_P1"]=cmatrix
    out["corr_MR_RP"]=cMRRP
    out["universe"]={"MR_crosses":MR_CROSSES,"RP_altbasket":RP_ALTBASKET,
                     "disjoint_from_P1":True}

    print("\n"+"="*74)
    print("総括:")
    print(f"  MR(別クロス): {out['MR_crosses']['grade']}   RP(別バスケット): {out['RP_altbasket']['grade']}")
    print(f"  第2ポート合成 vs 現行: corr {cmatrix['P2_combo']}  ← 低相関なら『真に並走できる第2口座』")
    print("  ※判定がADOPT未満でも現行同様 STRONG-LEAD は『質は高いが確証のみ不足』。確証はデモ前進検証(docs/29)で。")
    print("  ※数字は盛らない。相関が高い/ゲート未達なら、別ユニバースの再選定が必要(本スクリプトを再実行)。")
    print("="*74)
    try:
        path=(DRIVE_BASE+"/portfolio2_validate.json") if DRIVE_OK else "research/results/portfolio2_validate.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
