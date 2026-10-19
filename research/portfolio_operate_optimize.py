# -*- coding: utf-8 -*-
"""portfolio_operate_optimize.py — 確証済みエッジ(v7/v4/E5/E-Mon)＋S-Jul(7月overlay)で
効率的フロンティアと2口座ジョイントMCをワンショット再導出(Yahoo日足10年・Drive不要・再現的)。
規律: 数字は盛らない。Yahoo日足近似(v7/v4は日足proxy=Dukascopy確定値と差)・月次解像度=失格は楽観・
S-Jul N=10年=低検出力。相対比較が主眼、絶対値はDrive+デモで確定。out=results/portfolio_operate_optimize.json"""
import os, sys, json, urllib.request, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
DATA=os.path.join(HERE,"data")
os.makedirs(DATA, exist_ok=True)
P1,P2=1451606400,1767225599
YS={**{f:f+"=X" for f in ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]},
    "NAS100":"%5EIXIC","US500":"%5EGSPC","GER40":"%5EGDAXI","XAUUSD":"GC=F"}
def fetch(name):
    p=os.path.join(DATA,f"{name}_d.csv")
    if os.path.exists(p): return
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{YS[name]}?interval=1d&period1={P1}&period2={P2}"
    d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=25).read())
    r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        from datetime import datetime,timezone
        rows.append((datetime.fromtimestamp(t,timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
    import csv
    with open(p,"w",newline="") as f:
        w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"]); w.writerows(rows)
for nm in YS: fetch(nm)
print("fetched:", sorted(YS))

# ---- inlined builders (parallel_vs_existing_compare.py) ----
EMON=["NAS100","US500","GER40"]; E5_BASKET=["XAUUSD","US500","NAS100","GER40"]
YEN=["EURJPY","GBPJPY","USDJPY"]; V4=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
def load_daily(name,crypto=False):
    df=pd.read_csv(os.path.join(DATA,f"{name}_d.csv")); df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t"); df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
    df=df.groupby("trade_date",as_index=True).last(); df["weekday"]=df.index.dayofweek
    if not crypto: df=df[df["weekday"]<=4]
    df["o2o"]=df["open"].shift(-1)/df["open"]-1.0; return df
def to_monthly(r):
    s=r.copy(); s.index=pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()
def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def v7_monthly():
    acc=None
    for p in YEN:
        df=load_daily(p); m=to_monthly((df[df["weekday"]==0]["o2o"]-2*pip_size(p)/df[df["weekday"]==0]["open"]).dropna())
        acc=m if acc is None else acc.add(m,fill_value=0.0)
    return (acc/3.0).rename("v7")
def emon_monthly():
    parts=[(load_daily(nm)[load_daily(nm)["weekday"]==0]["o2o"]-3e-4).rename(nm) for nm in EMON]
    w=pd.concat(parts,axis=1).mean(axis=1,skipna=True).dropna(); return to_monthly(w).rename("E-Mon")
def e5_monthly():
    closes={}
    for nm in E5_BASKET:
        df=load_daily(nm); s=df["close"]; s.index=pd.to_datetime(df.index); closes[nm]=s.resample("ME").last()
    px=pd.DataFrame(closes).dropna(); ret=px.pct_change(); sig=pd.DataFrame(0.0,index=px.index,columns=px.columns)
    for lb in (1,3,6,12): sig=sig.add(np.sign(px.pct_change(lb)),fill_value=0)
    pos=np.sign(sig).shift(1); out=((pos*ret).mean(axis=1)-5e-4).dropna(); out.index=out.index.to_period("M"); return out.rename("E5")
def rsi_wilder(c,n=14):
    d=np.diff(c,prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    au=np.empty_like(c); ad=np.empty_like(c); au[0]=up[0]; ad[0]=dn[0]; a=1.0/n
    for i in range(1,len(c)): au[i]=a*up[i]+(1-a)*au[i-1]; ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=au/np.where(ad==0,1e-12,ad); return 100-100/(1+rs)
def atr_daily(h,l,c,n=14):
    pc=np.roll(c,1); pc[0]=c[0]; tr=np.maximum(h-l,np.maximum(np.abs(h-pc),np.abs(l-pc)))
    out=np.empty_like(tr); out[0]=tr[0]; a=1.0/n
    for i in range(1,len(tr)): out[i]=a*tr[i]+(1-a)*out[i-1]
    return out
def v4_monthly():
    monthly={}
    for p in V4:
        df=load_daily(p); o=df["open"].values; h=df["high"].values; l=df["low"].values; c=df["close"].values
        idx=df.index; n=len(c); rsi=rsi_wilder(c,14); atr=atr_daily(h,l,c,14); bbwin=20; cost=2*pip_size(p); i=bbwin+2
        while i<n-1:
            win=c[i-bbwin:i]; mean=win.mean(); sd=win.std(ddof=1); zz=(c[i]-mean)/sd if sd>0 else 0.0
            down=0
            for k in range(0,12):
                if i-k-1>=0 and c[i-k]<c[i-k-1]: down+=1
                else: break
            up=0
            for k in range(0,12):
                if i-k-1>=0 and c[i-k]>c[i-k-1]: up+=1
                else: break
            ret=(c[i]-c[i-1])/c[i-1] if c[i-1] else 0.0; mv=0.005
            buy=int(rsi[i]<35)+int(zz<-1.5)+int(down>=3)+int(ret<-mv); sell=int(rsi[i]>65)+int(zz>1.5)+int(up>=3)+int(ret>mv)
            sig=1 if (buy>=4 and buy>sell) else (-1 if (sell>=4 and sell>buy) else 0)
            if sig==0: i+=1; continue
            entry=o[i+1]; sld=1.5*atr[i]; tpd=1.2*sld
            if sld<=0: i+=1; continue
            sl=entry-sig*sld; tp=entry+sig*tpd; exit_px=None; j=i+1; held=0
            while j<n and held<8:
                hi=h[j]; lo=l[j]
                if sig>0:
                    if lo<=sl: exit_px=sl; break
                    if hi>=tp: exit_px=tp; break
                else:
                    if hi>=sl: exit_px=sl; break
                    if lo<=tp: exit_px=tp; break
                j+=1; held+=1
            if exit_px is None: exit_px=c[min(j,n-1)]
            r=sig*(exit_px/entry-1.0)-cost/entry; mkey=pd.Period(idx[min(j,n-1)],freq="M")
            monthly[mkey]=monthly.get(mkey,0.0)+r; i=max(i+1,j)
    return pd.Series(monthly).sort_index().rename("v4")
def sjul_july_per_year():
    """S-Jul: US500+NAS100 を7月だけLONG(月初open→月末close)、年ごとの平均7月益。"""
    vals=[]
    yrs=None
    per={}
    for nm in ["US500","NAS100"]:
        df=load_daily(nm); s=df["close"].copy(); s.index=pd.to_datetime(df.index)
        for y,g in s.groupby(s.index.year):
            jul=g[g.index.month==7]
            if len(jul)>=2:
                r=jul.iloc[-1]/jul.iloc[0]-1.0; per.setdefault(y,[]).append(r)
    return np.array([np.mean(v) for y,v in sorted(per.items()) if len(v)==2])

# ---- core (tested) ----
# --- core(自己テスト済) ---
def znorm(M, target=0.01):
    return M / M.std() * target

def port_series(Z, w):       # w: dict name->weight (sum~1)
    return (Z * pd.Series(w)).sum(axis=1)

def metrics(s, ann=12):
    s = pd.Series(s).dropna()
    if len(s) < 2: return dict(sharpe=0.0, maxDD=0.0, calmar=0.0, ann6=0.0, n=len(s))
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax())/eq.cummax()).min())*100
    mu = s.mean()*ann; vol = s.std()*np.sqrt(ann); shp = mu/vol if vol > 0 else 0.0
    cagr = (eq.iloc[-1]**(ann/len(s))-1)*100 if eq.iloc[-1] > 0 else -100
    cal = cagr/abs(dd) if dd else 0.0
    return dict(sharpe=round(float(shp),3), maxDD=round(dd,1), calmar=round(float(cal),2),
                ann6=round(6.0*float(cal),1), n=int(len(s)))

def sjul_overlay(Z, base_series, w_index_names, sjul_vals, factor):
    """7月の行にだけ S-Jul 益 ×factor を上乗せ(指数系の月のみ。連続重みにしない)。"""
    s = base_series.copy()
    if factor <= 0 or sjul_vals is None or len(sjul_vals) == 0: return s
    add = float(np.mean(sjul_vals)) * factor
    jul = pd.Index([p for p in s.index if getattr(p, "month", None) == 7])
    s.loc[jul] = s.loc[jul] + add
    return s

def search(Z, n=40000, cap=0.50, seed=20260610, objective="sharpe"):
    """Dirichlet探索で max-objective の重み(各重み<=cap=分散強制)。"""
    rng = np.random.default_rng(seed); k = Z.shape[1]; best = (-9, None)
    for _ in range(n):
        w = rng.dirichlet(np.ones(k))
        if cap is not None and w.max() > cap: continue
        m = metrics(port_series(Z, dict(zip(Z.columns, w))))
        if m[objective] > best[0]: best = (m[objective], w)
    return dict(zip(Z.columns, np.round(best[1], 3))) if best[1] is not None else None

def risk_parity(Z):
    w = np.ones(Z.shape[1]) / Z.shape[1]   # Z は等ボラ標準化済 → 等加重=リスクパリティ近似
    return dict(zip(Z.columns, np.round(w, 3)))

def oos_robust(M, names, weights, frac=0.70):
    """IS(前frac)で決めた重みをOOS(後)に固定適用し metrics 比較。"""
    Z = znorm(M[names].dropna()); h = int(len(Z)*frac)
    IS, OOS = Z.iloc[:h], Z.iloc[h:]
    return dict(IS=metrics(port_series(IS, weights)), OOS=metrics(port_series(OOS, weights)))

def twobook_jointloss(bookA, bookB, scale=1.0, target=0.08, max_loss=0.10,
                      n_paths=40000, cap=18, block=3, seed=7):
    """月次ブロックブートストラップで2口座のジョイントMC: ≥1通過率/両喪失率/相関。"""
    a = pd.Series(bookA).dropna(); b = pd.Series(bookB).dropna()
    idx = a.index.intersection(b.index); a, b = a.loc[idx].values*scale, b.loc[idx].values*scale
    n = len(a); rng = np.random.default_rng(seed)
    rho = float(np.corrcoef(a, b)[0, 1]) if n > 2 else float("nan")
    p1 = both_loss = 0
    for _ in range(n_paths):
        seqA, seqB = [], []
        while len(seqA) < cap:
            st = rng.integers(0, n)
            seqA.extend(a[(st+k) % n] for k in range(block)); seqB.extend(b[(st+k) % n] for k in range(block))
        passA = passB = lossA = lossB = False; eqA = eqB = 1.0
        for m in range(cap):
            eqA *= (1+seqA[m]); eqB *= (1+seqB[m])
            if not lossA and eqA <= 1-max_loss: lossA = True
            if not lossB and eqB <= 1-max_loss: lossB = True
            if not passA and not lossA and eqA >= 1+target: passA = True
            if not passB and not lossB and eqB >= 1+target: passB = True
        if passA or passB: p1 += 1
        if lossA and lossB and not (passA or passB): both_loss += 1
    return dict(rho=round(rho,3), pass_ge1_pct=round(100*p1/n_paths,1),
                both_loss_pct=round(100*both_loss/n_paths,1))

comp={"v7":v7_monthly(),"v4":v4_monthly(),"E5":e5_monthly(),"E-Mon":emon_monthly()}
M=pd.DataFrame(comp).dropna(how="all")
names=["v7","v4","E5","E-Mon"]; Mc=M[names].dropna()
Z=znorm(Mc)
sjul=sjul_july_per_year()

print("="*76); print("運用最適化(再導出) — Yahoo日足10年・実データ / S-Jul 7月overlay込み"); print("="*76)
print("\n[相関行列]"); print(Mc.corr().round(2).to_string())
print(f"\n[成分span] {Mc.index.min()}..{Mc.index.max()}  n={len(Mc)}ヶ月")
P0=metrics(port_series(znorm(M[['v7','v4','E5']].dropna()),{'v7':.4,'v4':.4,'E5':.2}))
print("\n[P0 既存 v7:v4:E5=40:40:20]:", P0)
rp=risk_parity(Z); ms=search(Z,n=40000,cap=0.50,objective="sharpe"); mc=search(Z,n=40000,cap=0.50,objective="calmar")
print("\n[配分候補(各重み<=0.50で分散強制)]")
print("  risk_parity:", rp, "->", metrics(port_series(Z,rp)))
print("  max_sharpe :", ms, "->", metrics(port_series(Z,ms)))
print("  max_calmar :", mc, "->", metrics(port_series(Z,mc)))
print("\n[OOS頑健性(IS70%で決め OOS30%固定適用)]")
for tag,w in [("risk_parity",rp),("max_sharpe",ms),("max_calmar",mc)]:
    r=oos_robust(M,names,w); print(f"  {tag:11s} IS:{r['IS']}  OOS:{r['OOS']}")

print("\n[S-Jul 7月overlay の効果(指数book=E-Mon主軸に上乗せ)]")
bookB_base=port_series(znorm(M[['E-Mon','E5']].dropna()),{'E-Mon':.65,'E5':.35})
for fac in [0.0,1.0,2.0]:
    sb=sjul_overlay(znorm(M[['E-Mon','E5']].dropna()),bookB_base,["E-Mon"],sjul,factor=fac)
    print(f"  factor={fac}: {metrics(sb)}  (mean S-Jul 7月益={np.mean(sjul)*100:.1f}% n={len(sjul)})")

print("\n[2口座ジョイントMC: A=v4+v7 / B=E-Mon+E5, scale=中央3相当2.6x, cap18ヶ月]")
A=port_series(znorm(M[['v4','v7']].dropna()),{'v4':.55,'v7':.45})
B0=bookB_base
Bsj=sjul_overlay(znorm(M[['E-Mon','E5']].dropna()),bookB_base,["E-Mon"],sjul,factor=2.0)
print("  S-Julなし:", twobook_jointloss(A,B0,scale=2.6,n_paths=40000,cap=18))
print("  S-Julあり:", twobook_jointloss(A,Bsj,scale=2.6,n_paths=40000,cap=18))

out=dict(span=f"{Mc.index.min()}..{Mc.index.max()}",n_months=len(Mc),corr=Mc.corr().round(3).to_dict(),
         P0=P0,risk_parity={'w':rp,'m':metrics(port_series(Z,rp))},
         max_sharpe={'w':ms,'m':metrics(port_series(Z,ms))},max_calmar={'w':mc,'m':metrics(port_series(Z,mc))},
         sjul_mean_july=round(float(np.mean(sjul)),4),sjul_n=int(len(sjul)),
         twobook_noSjul=twobook_jointloss(A,B0,scale=2.6,n_paths=20000,cap=18),
         twobook_Sjul=twobook_jointloss(A,Bsj,scale=2.6,n_paths=20000,cap=18))
os.makedirs(os.path.join(HERE,"results"),exist_ok=True)
json.dump(out,open(os.path.join(HERE,"results","portfolio_operate_optimize.json"),"w"),ensure_ascii=False,indent=2,default=str)
print("\n保存: research/results/portfolio_operate_optimize.json")
