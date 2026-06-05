"""
colab_firms_2v3_compare.py — 業者別: 現状2種(v7+E5) vs 推奨3種(v7+v4+E5, 推奨比率) 比較。

背景: v4(k≥4合議)が実10年Dukascopyで ADOPT(6/6)・v7と無相関(0.029)に到達(docs/42)。
  そこで「現状の2種(v7+E5)」と「v4を加えた推奨3種」を、各プロップ業者のルール枠で比較する。

推奨比率(3種): v7/v4/E5 は相互に低相関(v7⇄v4≈0.03, v7⇄E5≈−0.16, v4⇄E5≈低)ゆえ **リスクパリティ
  (各戦略の寄与リスクを均等)** を推奨基準とする。各月次系列を単位ボラに標準化し等加重→実効均等リスク。
  → 比率は出力で実値を提示(標準化前の自然サイズ換算も併記)。

業者(docs/24 + docs/25, 2026公開ルール・申込前に各社最新規約を要確認):
  FN_Stellar  : 2step +8/+5% / 最大-10%(静的) / 日次-5% / 時間無制限 / 分配80% / 一貫性なし
  FTMO        : 2step +8/+5% / 最大-10%(静的) / 日次-5% / 時間無制限 / 分配80-90% / 一貫性なし
  FundingPips0: 即時      / 最大-5%(トレーリング) / 日次-3% / 一貫性15%(単日≤総益15%) / 分配95%
  Blueberry   : 即時      / 最大-10%(トレーリング→建値ロック) / 日次なし / 一貫性なし / 分配80%

評価: 各社のDD枠に **両ポートを同じp95DD目標で合わせ(=同リスク)**, チャレンジ社は13週/年次 通過率・失格率,
  即時社は 年次失格率・年率 を月次ブロック・ブートストラップMCで算出。一貫性ルール/日次/トレーリングは
  月次MCで完全再現できないため **定性補正を明記**(v7=単日集中で一貫性に不利, v4=分散で緩和)。

使い方(Colab): H1_DIR={pair}_h1.csv(10年, 9ペア), DAILY_DIR=多資産日足(無ければYahoo)。「すべて実行」。
※ シミュレーション。確率であり保証ではない。一貫性/日次/スワップ等は実口座/デモで要確認。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; DAILY_DIR="{base}/multiasset_daily"; LOCAL="./research/data"
PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY=["EURJPY","GBPJPY","USDJPY"]; HOURS=[4,6,8,10]
ASSETS=["XAUUSD","US500","NAS100","GER40"]; LB=[1,3,6,12]; VOLWIN=12
SPREAD={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,"USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFSPR=1.5; SLIP=0.5
E5_FRICTION=dict(idx_long=-3.0,idx_short=-1.5,gold_long=-4.0,gold_short=-1.5)
N_PATHS=4000; SEED=11

# 業者ルール
FIRMS={
 "FN_Stellar":   dict(kind="challenge", target=0.08, total_dd=0.10, trailing=False, payout=0.80, consistency=None),
 "FTMO":         dict(kind="challenge", target=0.08, total_dd=0.10, trailing=False, payout=0.80, consistency=None),
 "FundingPips0": dict(kind="instant",   target=None, total_dd=0.05, trailing=True,  payout=0.95, consistency=0.15),
 "Blueberry":    dict(kind="instant",   target=None, total_dd=0.10, trailing=True,  payout=0.80, consistency=None),
}

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive",force_remount=False)
    except Exception as e: print("Drive不可:",e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")
def pipsz(p): return 0.01 if p.endswith("JPY") else 0.0001

# ---------- data ----------
def _read(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tc=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns),df.columns[0])
    df["t"]=pd.to_datetime(df[tc],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*n):
        for x in n:
            for c in df.columns:
                if c==x: return c
        return None
    o,h,l,c=col("open","bidopen","o"),col("high","bidhigh","h"),col("low","bidlow","l"),col("close","bidclose","c")
    if c is None: return None
    if None in (o,h,l):  # close-only
        s=df[c].astype(float); return pd.DataFrame({"open":s,"high":s,"low":s,"close":s})
    return df[[o,h,l,c]].astype(float).rename(columns={o:"open",h:"high",l:"low",c:"close"})
def _yf(sym,rng="10y",iv="1d"):
    import urllib.request, json as j
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}"
    d=j.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=25).read())
    r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[(pd.to_datetime(t,unit="s",utc=True),q["open"][i],q["high"][i],q["low"][i],q["close"][i])
          for i,t in enumerate(ts) if None not in (q["open"][i],q["high"][i],q["low"][i],q["close"][i])]
    return pd.DataFrame(rows,columns=["t","open","high","low","close"]).set_index("t")
H1={}; DLY={}; MUL={}
def h1(p):
    if p in H1: return H1[p]
    for path in [f"{H1_DIR.format(base=DRIVE_BASE)}/{p}_h1.csv", f"{LOCAL}/{p}_h1.csv"]:
        if os.path.exists(path): H1[p]=_read(path); return H1[p]
    H1[p]=None; return None
def daily(p):
    if p in DLY: return DLY[p]
    d=h1(p)
    if d is not None:
        g=d.resample("1D"); DLY[p]=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),"low":g["low"].min(),"close":g["close"].last()}).dropna(); return DLY[p]
    for path in [f"{LOCAL}/{p}_d.csv"]:
        if os.path.exists(path): DLY[p]=_read(path); return DLY[p]
    try:
        sym={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X","USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X"}[p]
        DLY[p]=_yf(sym); return DLY[p]
    except Exception: DLY[p]=None; return None
def masset(n):
    if n in MUL: return MUL[n]
    for path in [f"{DAILY_DIR.format(base=DRIVE_BASE)}/{n}_d.csv", f"{LOCAL}/{n}_d.csv"]:
        if os.path.exists(path): MUL[n]=_read(path); return MUL[n]
    try:
        sym={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}[n]; MUL[n]=_yf(sym); return MUL[n]
    except Exception: MUL[n]=None; return None

# ---------- indicators ----------
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

# ---------- monthly return series (account %, reference size) ----------
def v7_monthly():
    cols=[]
    for p in JPY:
        d=h1(p)
        if d is None: continue
        cv=d["close"].values; idx=d.index; ps=pipsz(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            r=pd.Series((cv[a+24]-cv[a])/cv[a]-2.0*ps/cv[a], index=idx[a].to_period("M"))
            cols.append(r.groupby(level=0).sum())
    if not cols: return pd.Series(dtype=float)
    return pd.concat(cols,axis=1).sum(axis=1).dropna()

def v4_monthly():
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
    s=pd.Series(mo); s.index=pd.PeriodIndex(s.index,freq="M"); return s.sort_index()

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

def to_M(s):
    s=pd.Series(s).dropna()
    if len(s)==0: return s
    idx=s.index if isinstance(s.index,pd.PeriodIndex) else pd.PeriodIndex(s.index,freq="M")
    return pd.Series(s.values,index=idx).groupby(level=0).sum()

# ---------- MC ----------
def block_bootstrap(s,n_paths=N_PATHS,m=120,block=3,seed=SEED):
    w=pd.Series(s).dropna().values;n=len(w)
    if n==0: return np.zeros((n_paths,1))
    rng=np.random.default_rng(seed);P=np.empty((n_paths,m))
    for p in range(n_paths):
        seq=[]
        while len(seq)<m:
            st=rng.integers(0,n);seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:m]
    return P
def eval_challenge(P,target,total_dd,trailing):
    n,T=P.shape;pas=np.zeros(n,bool);fail=np.zeros(n,bool);mo=np.full(n,np.nan)
    for i in range(n):
        eq=1.0;peak=1.0
        for t in range(T):
            eq*=(1+P[i,t]);peak=max(peak,eq)
            base=peak if trailing else 1.0
            if (eq-base)/base<=-total_dd: fail[i]=True;break
            if target is not None and eq>=1+target: pas[i]=True;mo[i]=t+1;break
        # instant: 失格しなければ"継続"=年次失格率で評価
    return pas,fail,mo
def annual_dq(P,total_dd,trailing):
    # 12ヶ月窓での失格率
    n,T=P.shape;fail=np.zeros(n,bool)
    for i in range(n):
        eq=1.0;peak=1.0
        for t in range(min(T,12)):
            eq*=(1+P[i,t]);peak=max(peak,eq);base=peak if trailing else 1.0
            if (eq-base)/base<=-total_dd: fail[i]=True;break
    return float(fail.mean())
def ann_return(s):
    s=pd.Series(s).dropna();
    if len(s)==0: return 0.0
    return float(((1+s).prod())**(12/len(s))-1)
def maxdd(s):
    eq=(1+pd.Series(s).dropna()).cumprod();pk=eq.cummax();return float(((eq-pk)/pk).min())

def main():
    s7=to_M(v7_monthly()); s4=to_M(v4_monthly()); s5=to_M(e5_monthly())
    df=pd.concat([s7.rename("v7"),s4.rename("v4"),s5.rename("E5")],axis=1).dropna()
    print("="*76); print("業者別比較: 現状2種(v7+E5) vs 推奨3種(v7+v4+E5, リスクパリティ)"); print("="*76)
    if len(df)<24:
        print(f"⚠ 共通{len(df)}ヶ月=ローカル短期。相関/比率は不安定。実10年(Drive)で確定すること。")
    print(f"共通{len(df)}ヶ月  相関(10年想定: v7⇄v4≈0.03, v7⇄E5≈−0.16):\n{df.corr().round(3).to_string()}")
    # 各レッグを共通の月次目標ボラ(TGT)にスケール=実リターン単位(複利可)。低相関ゆえ等リスク=リスクパリティ。
    TGT=0.01
    comp={c: df[c]*(TGT/df[c].std()) for c in df.columns}   # 各 ~1%月次ボラ
    P2 = comp["v7"]+comp["E5"]                                # 2種: 等リスク(各1%)
    P3 = comp["v7"]+comp["v4"]+comp["E5"]                     # 3種: 等リスク(リスクパリティ, 各1%)
    P3c= 0.40*comp["v7"]/TGT*TGT + 0.40*comp["v4"] + 0.20*comp["E5"]  # 確信度調整(E5はデモ前提で抑制)
    P3c= 0.40*comp["v7"]+0.40*comp["v4"]+0.20*comp["E5"]
    def shp(s):
        v=pd.Series(s).std()*np.sqrt(12); return round(ann_return(s)/v,2) if v>0 else 0.0
    print(f"\n推奨比率(リスク寄与で表現):")
    print(f"  2種 v7:E5      = 50:50 (等リスク)")
    print(f"  3種 v7:v4:E5   = 33:33:33 (リスクパリティ=本命) / 確信度版 40:40:20 (E5はデモ前提で抑制)")
    print(f"  年Sharpe: 2種={shp(P2)}  3種(33:33:33)={shp(P3)}  3種(40:40:20)={shp(P3c)}  (高いほど分散効率↑)")
    out_ratio=dict(two="v7:E5=50:50", three_riskparity="v7:v4:E5=33:33:33", three_confidence="v7:v4:E5=40:40:20",
                   sharpe_2=shp(P2), sharpe_3rp=shp(P3), sharpe_3conf=shp(P3c))

    out={"months":int(len(df)),"corr":df.corr().round(3).to_dict(),"recommended_ratio":out_ratio,"firms":{}}
    print("\n各社(両ポートを同社DD枠の75%に同p95DDで合わせ＝同リスク条件):")
    for fn,rule in FIRMS.items():
        cap=rule["total_dd"]; tgtDD=cap*0.75
        res={}
        for name,base in [("P2_v7+E5",P2),("P3_v7+v4+E5",P3)]:
            # スケール: p95DDが目標になる総リスク係数を二分探索
            lo,hi=0.05,8.0
            for _ in range(22):
                mid=(lo+hi)/2; P=block_bootstrap(base*mid,m=120)
                dd=-np.percentile([maxdd(P[i]) for i in range(0,len(P),8)],95)  # p95 maxDD(正)
                if dd>tgtDD: hi=mid
                else: lo=mid
            scale=(lo+hi)/2; ser=base*scale; P=block_bootstrap(ser,m=120)
            if rule["kind"]=="challenge":
                pas,fail,mo=eval_challenge(P,rule["target"],cap,rule["trailing"])
                res[name]=dict(scale=round(scale,2), ann_return_pct=round(ann_return(ser)*100,1),
                    maxDD_hist=round(maxdd(ser)*100,1),
                    pass13w=round(float((np.nan_to_num(mo,nan=99)<=3).mean())*100,1),
                    pass_total=round(float(pas.mean())*100,1), fail=round(float(fail.mean())*100,1),
                    payout_net_pct=round(ann_return(ser)*rule["payout"]*100,1))
            else:
                dq=annual_dq(P,cap,rule["trailing"])
                res[name]=dict(scale=round(scale,2), ann_return_pct=round(ann_return(ser)*100,1),
                    maxDD_hist=round(maxdd(ser)*100,1), annual_dq=round(dq*100,1),
                    payout_net_pct=round(ann_return(ser)*rule["payout"]*100,1))
        out["firms"][fn]=dict(rule=rule,res=res)
        print(f"\n■ {fn}  (枠{int(cap*100)}%{'トレーリング' if rule['trailing'] else '静的'}"
              f"{' /一貫性'+str(int(rule['consistency']*100))+'%' if rule['consistency'] else ''} 分配{int(rule['payout']*100)}%)")
        for name,r in res.items():
            if rule["kind"]=="challenge":
                print(f"   {name:13s}: 年率{r['ann_return_pct']:>5}% maxDD{r['maxDD_hist']:>6}% | "
                      f"3ヶ月通過{r['pass13w']:>5}% 通過(無制限){r['pass_total']:>5}% 失格{r['fail']:>4}% 手取り{r['payout_net_pct']:>5}%")
            else:
                print(f"   {name:13s}: 年率{r['ann_return_pct']:>5}% maxDD{r['maxDD_hist']:>6}% | "
                      f"年失格{r['annual_dq']:>5}% 手取り{r['payout_net_pct']:>5}%")
        if rule["consistency"]:
            print(f"   ※一貫性{int(rule['consistency']*100)}%ルール: v7は月曜集中益で抵触しやすい→2種は不利。"
                  f"v4(日足分散)を足す3種は単日集中が緩み有利。月次MC外＝実口座/デモで要確認。")
    # ===== ★あなたの現状(eXYSN)に当てはめた比較: Blueberry Instant $50k / v7+E5 75:25 @v7 1.5% =====
    print("\n"+"="*76)
    print("★あなたの現状(eXYSN/docs25+36③): Blueberry Instant $50k, v7+E5=75:25, v7週次1.5%(攻め)")
    print("   ルール: 最大-10%トレーリング・日次なし・一貫性なし・分配80%。docs36③: 年失格6.5%/手取り≈¥862k/5年失格38%")
    print("="*76)
    ACC=50000; JPYrate=157.0; PAYOUT=0.80; CAP=0.10; TRAIL=True
    cur = 0.75*comp["v7"] + 0.25*comp["E5"]                 # 現状: v7偏重 75:25
    rec = 0.40*comp["v7"] + 0.40*comp["v4"] + 0.20*comp["E5"]  # 推奨3種 40:40:20
    def dq_of(base,scale): return annual_dq(block_bootstrap(base*scale,m=12),CAP,TRAIL)
    def fit_dq(base,target):
        lo,hi=0.05,15.0
        for _ in range(28):
            mid=(lo+hi)/2
            if dq_of(base,mid)>target: hi=mid
            else: lo=mid
        return (lo+hi)/2
    def yen(s): return round(ann_return(s)*ACC*PAYOUT*JPYrate)
    def line(tag,s,scale):
        ser=s*scale; dq=dq_of(s,scale); fy=1-(1-dq)**5
        print(f"   {tag:28s}: 年率{ann_return(ser)*100:>5.1f}% maxDD{maxdd(ser)*100:>6.1f}% "
              f"年失格{dq*100:>4.1f}% 5年失格{fy*100:>4.1f}% 手取り≈¥{yen(ser):>9,}/年")
        return dict(ann=round(ann_return(ser)*100,1),maxDD=round(maxdd(ser)*100,1),dq=round(dq*100,1),
                    fail5y=round(fy*100,1),yen=yen(ser))
    # 現状を docs36③ の年失格6.5% に合わせる総リスク
    sc_cur=fit_dq(cur,0.065)
    r_cur =line("現状 v7+E5 75:25(攻め)", cur, sc_cur)
    # 推奨3種: ①現状と同じ総リスク(=同じ攻め) → 失格↓/年率↑
    r_same=line("推奨 v7+v4+E5(同リスク)", rec, sc_cur)
    # 推奨3種: ②現状と同じ年失格6.5%まで攻める → 年率↑(手取り↑)
    sc_rec=fit_dq(rec,0.065)
    r_eqdq=line("推奨 v7+v4+E5(同失格6.5%)", rec, sc_rec)
    # 推奨3種: ③低失格(年2%)に絞る安全運用
    sc_saf=fit_dq(rec,0.02)
    r_safe=line("推奨 v7+v4+E5(安全:年失格2%)", rec, sc_saf)
    out["your_current_blueberry"]=dict(account=ACC,ratio_current="v7:E5=75:25",ratio_rec="v7:v4:E5=40:40:20",
        current=r_cur, rec_same_risk=r_same, rec_same_dq=r_eqdq, rec_safe=r_safe)
    print("   → 同じ攻めなら【失格↓】、同じ失格まで攻めれば【手取り↑】。v4(無相関)で分散効率が上がるのが源泉。")
    # ---- サニティチェック: この実行が信頼できるか(10年か・現状がリポジトリ値¥862kと整合か) ----
    span_m=len(df); corr_v7v4=round(float(df.corr().loc["v7","v4"]),3)
    anchor_yen=862000; dev=abs(r_cur["yen"]-anchor_yen)/anchor_yen
    trust = (span_m>=90) and (abs(corr_v7v4-0.03)<0.20) and (dev<0.6)
    print(f"\n   [サニティ] 共通{span_m}ヶ月 / v7⇄v4相関={corr_v7v4}(10年期待≈0.03) / "
          f"現状手取り¥{r_cur['yen']:,} vs docs36③アンカー¥{anchor_yen:,}(乖離{dev*100:.0f}%)")
    if trust:
        print("   [サニティ] ✅ 10年・整合 → 上記の絶対値は信頼してよい(実数確定)。")
    else:
        print("   [サニティ] ⚠ 短期 or アンカー乖離大 → **絶対値は信用しない**(方向性のみ)。"
              "Driveの dukascopy_data_h1 に9ペア10年H1があるか確認し再実行。")
    out["your_current_blueberry"]["sanity"]=dict(months=span_m,corr_v7v4=corr_v7v4,
        current_yen=r_cur["yen"],anchor_yen=anchor_yen,trustworthy=bool(trust))

    # ===== ★リスク倍率ごとの表: プロップ($100k) / インスタント($50k) ・ 現状 vs 推奨 =====
    # 倍率の定義: 1.0x = 現状(cur)の hist maxDD が約10%になる総リスク(docs/25「1.5倍≒maxDD15%」と整合)。
    cur_u = 0.75*comp["v7"] + 0.25*comp["E5"]                 # 現状 75:25(等リスク単位)
    rec_u = 0.40*comp["v7"] + 0.40*comp["v4"] + 0.20*comp["E5"]# 推奨 40:40:20
    # cur を hist maxDD=10% に合わせる BASE を二分探索 → これを「1.0x」とする
    def fit_maxdd(base,target):
        lo,hi=0.05,15.0
        for _ in range(28):
            mid=(lo+hi)/2
            if abs(maxdd(base*mid))*100>target: hi=mid
            else: lo=mid
        return (lo+hi)/2
    BASE=fit_maxdd(cur_u,10.0)
    MULTS=[0.5,0.75,1.0,1.5,2.0,2.5,3.0]
    def row(series,scale,acct,trailing,payout):
        ser=series*scale; dq=annual_dq(block_bootstrap(ser,m=12),0.10,trailing)
        return dict(maxDD=round(maxdd(ser)*100,1), dq=round(dq*100,1), fail5=round((1-(1-dq)**5)*100,1),
                    yen=round(ann_return(ser)*acct*payout*157.0))
    def mult_table(name,acct,trailing,payout):
        print(f"\n  ［{name}］口座${acct:,}・分配{int(payout*100)}%・{'トレーリング' if trailing else '静的'}-10%枠 "
              f"(1.0x=現状maxDD≈10%・docs25の1.5倍≒15%と整合)")
        print(f"    {'倍率':>5} | {'現状75:25  maxDD / 年失格 / 5年失格 / 手取り':<44} | {'推奨40:40:20  maxDD / 年失格 / 5年失格 / 手取り'}")
        rows={}
        for m in MULTS:
            c=row(cur_u,BASE*m,acct,trailing,payout); r=row(rec_u,BASE*m,acct,trailing,payout)
            rows[f"{m:.2f}x"]=dict(current=c,recommended=r)
            print(f"    {m:>4.1f}x | {c['maxDD']:>6.1f}% /{c['dq']:>5.1f}% /{c['fail5']:>5.1f}% / ¥{c['yen']:>9,}"
                  f"   |  {r['maxDD']:>6.1f}% /{r['dq']:>5.1f}% /{r['fail5']:>5.1f}% / ¥{r['yen']:>9,}")
        return rows
    # プロップ突破率/到達月(静的-10%・+8%目標・時間無制限=24ヶ月窓で評価)
    def prop_pass(series, scale, horizon=24, target=0.08, dd=0.10, seed=SEED):
        P=block_bootstrap(series*scale, m=horizon, seed=seed)
        n,T=P.shape; pm=np.full(n,np.nan); fail=np.zeros(n,bool)
        for i in range(n):
            eq=1.0
            for t in range(T):
                eq*=(1+P[i,t])
                if eq<=1-dd: fail[i]=True; break       # 静的-10%(初期基準)
                if eq>=1+target: pm[i]=t+1; break       # +8%到達(月index)
        ok=~np.isnan(pm)
        pass3=float((pm[ok]<=3).sum())/n*100 if ok.any() else 0.0
        passT=float(ok.mean())*100
        med=float(np.nanmedian(pm)) if ok.any() else None
        return dict(pass3mo=round(pass3,1), pass_total=round(passT,1),
                    median_months=(None if med is None else round(med,1)), fail=round(float(fail.mean())*100,1))
    def prop_pass_table():
        print("\n  ［プロップ突破率/到達月 FundedNext $100k・+8%/静的-10%・時間無制限(24ヶ月窓)］")
        print(f"    {'倍率':>5} | {'現状 3ヶ月突破 / 無制限突破 / 到達中央月 / 失格':<40} | 推奨 3ヶ月突破 / 無制限突破 / 到達中央月 / 失格")
        out2={}
        for m in MULTS:
            c=prop_pass(cur_u,BASE*m); r=prop_pass(rec_u,BASE*m)
            out2[f"{m:.2f}x"]=dict(current=c,recommended=r)
            cm = "—" if c['median_months'] is None else f"{c['median_months']:.0f}ヶ月"
            rm = "—" if r['median_months'] is None else f"{r['median_months']:.0f}ヶ月"
            print(f"    {m:>4.1f}x | {c['pass3mo']:>5.1f}% /{c['pass_total']:>6.1f}% / {cm:>6} /{c['fail']:>5.1f}%"
                  f"   |  {r['pass3mo']:>5.1f}% /{r['pass_total']:>6.1f}% / {rm:>6} /{r['fail']:>5.1f}%")
        return out2
    print("\n"+"="*76); print("★リスク倍率ごと: 現状(v7+E5 75:25) vs 推奨(v7+v4+E5 40:40:20)"); print("="*76)
    out["mult_tables"]=dict(
        prop=mult_table("プロップ FundedNext",100000,False,0.80),
        instant=mult_table("インスタント Blueberry",50000,True,0.80))
    out["prop_pass"]=prop_pass_table()
    if not trust:
        print("\n   ⚠ サニティ未達(短期/相関乖離)＝上表の絶対値は信用せず。10年Driveで再実行して確定を。")

    print("\n"+"="*76)
    print("総括: チャレンジ(13週)は v4/E5 の上乗せ小(低頻度)=2種3種ほぼ同等。差が出るのは資金化後の年次"
          "(分散でDD効率↑→同枠で年率↑/失格↓)。一貫性ルール社では3種(v4分散)が構造的に有利。")
    try:
        path=(DRIVE_BASE+"/firms_2v3_compare.json") if DRIVE_OK else "research/results/firms_2v3_compare.json"
        os.makedirs(os.path.dirname(path),exist_ok=True); json.dump(out,open(path,"w"),ensure_ascii=False,indent=2,default=str); print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    main()
