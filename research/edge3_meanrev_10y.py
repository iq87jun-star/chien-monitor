"""
edge3_meanrev_10y.py — 3本目候補【平均回帰族】10年検定。新規事前登録 + 厳格ゲート + Bonferroni。

経緯: v7(円月曜LONG)生存、v8(CHF)/gotobi/TOM は10年で全滅(docs/17,20)。それらは全て
【順方向ドリフト】系。本探索は構造が直交する【平均回帰】族=行き過ぎの反動を狙う。生き残れば
v7と低相関の真の分散先になる。⚠勝率は低い前提(docs/20の教訓)。同じ規律で淡々と検定する。

事前登録候補(N=4, Bonferroni α=0.05/4=0.0125)。全て日次/週次の z-score 反転:
  z_t = (r_t - mean_W(r)) / std_W(r),  W=20。閾値1.5σ(事前固定・チューニングしない)。
  MR1 DAILY_YEN_BIDIR : 円3クロス。日次z<=-1.5→翌日LONG / z>=+1.5→翌日SHORT(1日保有)。双方向。
  MR2 DAILY_MAJ_BIDIR : 同 majors(EURUSD/GBPUSD/AUDUSD/USDCHF/USDCAD)。
  MR3 WEEKLY_YEN_BIDIR: 円。週次zで反転(1週保有)。
  MR4 DAILY_YEN_LONGONLY: 円。z<=-1.5→翌日LONGのみ(押し目買い。ショートswap回避)。
  PLC RANDOM_PLACEBO  : ★プラセボ。同頻度のランダム日にLONG。これが+なら反転シグナルは無意味。

ゲート(全て10年・採用は全通過):
  G_perm   順列 p <= Bonferroni α(0.0125)
  G_jk     ジャックナイフ max_p <= 0.10(年依存でない)
  G_oos    IS/OOS 両方で符号維持
  G_indep  v7(円月曜)月次相関 <= 0.4(できれば負=分散効果)
  G_plac   プラセボが非有意 かつ 候補 > プラセボ
  G_cost   往復1-4pipで純益+維持
ADOPT=全主要ゲート通過。1つも無ければ→3本目も見送り(v7一本確定)。

⚠ シミュレーション(日次/週次終値モデル)。DD/合格率はユーザーの足内エンジンで別途実測。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

COST_PIP = 2.0
YEN    = ["EURJPY","GBPJPY","USDJPY"]
MAJORS = ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD"]
W      = 20      # z-score窓(日/週)
Z      = 1.5     # 反転閾値σ(事前固定)

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル?):", e); USE_DRIVE=False

def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(pair):
    c=[]
    if USE_DRIVE:
        b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv"]
    c+=[f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None
def load(pair):
    path=_resolve(pair)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE={}
def H1(p):
    if p not in CACHE: CACHE[p]=load(p)
    return CACHE[p]
def have(p): return H1(p) is not None

def daily_close(pair):
    s=H1(pair)
    if s is None: return None
    return s.resample("1D").last().dropna()
def weekly_close(pair):
    s=H1(pair)
    if s is None: return None
    return s.resample("1W").last().dropna()

def mr_trades(pair, freq, bidir, z=Z, w=W, costpip=COST_PIP):
    """平均回帰: 終値リターンのz-score。z<=-z→次足LONG / (bidir)z>=+z→次足SHORT。1足保有。
       戻り: 取引リターン系列(index=シグナル日)。"""
    px = daily_close(pair) if freq=="D" else weekly_close(pair)
    if px is None or len(px)<w+5: return pd.Series(dtype=float)
    r = px.pct_change()
    mu= r.rolling(w).mean(); sd=r.rolling(w).std()
    zc=(r-mu)/sd
    nxt = px.shift(-1)/px - 1.0          # 次足の素リターン(エントリー=当足終値, 決済=次足終値)
    ps=pip(pair); cpr=costpip*ps/px
    out={}
    for t in px.index[:-1]:
        zt=zc.get(t,np.nan)
        if not np.isfinite(zt): continue
        if zt<=-z:   out[t]= nxt[t]-cpr[t]          # LONG
        elif bidir and zt>=z: out[t]= -nxt[t]-cpr[t] # SHORT
    return pd.Series(out).sort_index()

def random_placebo(pairs, freq, n_match, bidir, seed=7, costpip=COST_PIP):
    """同頻度・同本数のランダム日にエントリー。bidirなら売買方向もランダム(±1)=双方向戦略の正しい帰無。
       反転シグナルがランダムなタイミング/方向に勝てるかのプラセボ。"""
    rng=np.random.default_rng(seed); legs=[]
    for pair in pairs:
        px=daily_close(pair) if freq=="D" else weekly_close(pair)
        if px is None or len(px)<5: continue
        nxt=px.shift(-1)/px-1.0; ps=pip(pair); cpr=costpip*ps/px
        idx=px.index[:-1]; k=min(n_match//max(len(pairs),1), len(idx))
        pick=rng.choice(len(idx), size=k, replace=False)
        for i in pick:
            t=idx[i]; d=rng.choice([-1,1]) if bidir else 1
            legs.append((t, d*nxt[t]-cpr[t]))
    if not legs: return pd.Series(dtype=float)
    s=pd.Series([v for _,v in legs], index=[t for t,_ in legs])
    return s.groupby(s.index).mean().sort_index()

def combine(pairs, freq, bidir, **kw):
    cols=[mr_trades(p,freq,bidir,**kw) for p in pairs if have(p)]
    cols=[c for c in cols if len(c)]
    if not cols: return pd.Series(dtype=float)
    df=pd.concat(cols,axis=1)
    return df.mean(axis=1).dropna()   # 同日複数ペアは平均(等加重ポート)

def perm_p(r,n=5000,seed=13):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); s=np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n)])>=real).mean())
def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1),win_pct=round((x>0).mean()*100,0),maxDD_pct=round(dd,1),n=int(len(x)))
def jackknife(s):
    yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    jk={int(y):round(perm_p(s[s.index.year!=y].values),3) for y in yrs}
    return jk, round(max(jk.values()),3)
def monthly(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

def yen_monday_monthly():
    rows=[]
    for p in YEN:
        if not have(p): continue
        s=H1(p); cv=s.values; idx=s.index; ps=pip(p)
        for hr in (4,6,8,10):
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a: rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-COST_PIP*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

def candidates():
    return {
        "MR1_DAILY_YEN_BIDIR":   lambda cp=COST_PIP: combine(YEN,   "D", True,  costpip=cp),
        "MR2_DAILY_MAJ_BIDIR":   lambda cp=COST_PIP: combine(MAJORS,"D", True,  costpip=cp),
        "MR3_WEEKLY_YEN_BIDIR":  lambda cp=COST_PIP: combine(YEN,   "W", True,  costpip=cp),
        "MR4_DAILY_YEN_LONGONLY":lambda cp=COST_PIP: combine(YEN,   "D", False, costpip=cp),
    }

def run():
    avail=[p for p in YEN+MAJORS if have(p)]
    print("利用可能ペア:", avail)
    C=candidates(); N=len(C); bonf=round(0.05/N,4)
    ym=yen_monday_monthly()
    out={"meta":dict(n_candidates=N, bonferroni_alpha=bonf, W=W, Z=Z, available=avail),"candidates":{}}
    print(f"\n試行数N={N} Bonferroniα={bonf}  (z窓W={W}, 閾値Z={Z}σ)")
    for name,fn in C.items():
        s=fn()
        if len(s)<30:
            out["candidates"][name]=dict(note="insufficient",n=len(s)); print(f"\n{name}: データ不足 n={len(s)}"); continue
        st=stats(s); p=round(perm_p(s.values),4)
        jk=jackknife(s); jkmax=jk[1] if jk else None
        h=s.index[len(s)//2]; isr,oos=s[s.index<h],s[s.index>=h]
        ms=monthly(s); j=pd.concat([ms.rename("c"),ym.rename("y")],axis=1).dropna()
        corr=round(float(j["c"].corr(j["y"])),2) if len(j)>12 else None
        # マッチしたプラセボ(同頻度・同本数LONG)
        freq="W" if "WEEKLY" in name else "D"; pairs=YEN if "YEN" in name else MAJORS
        is_bidir="LONGONLY" not in name
        plc=random_placebo(pairs, freq, len(s), is_bidir); plc_p=round(perm_p(plc.values),3); plc_net=stats(plc)["net_pct"]
        cost={f"{c}pip":stats(fn(float(c)))["net_pct"] for c in (1,2,3,4)}
        g_perm=p<=bonf; g_jk=(jkmax is not None and jkmax<=0.10)
        g_oos=(isr.sum()>0 and oos.sum()>0); g_indep=(corr is None) or abs(corr)<=0.4
        g_plac=(plc_p>0.05 and st["net_pct"]>plc_net); g_cost=all(v>0 for v in cost.values())
        passed=sum([g_perm,g_jk,g_oos,g_indep,g_plac,g_cost])
        grade="ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac) else ("LEAD" if (st["net_pct"]>0 and p<=0.10) else "REJECT")
        out["candidates"][name]=dict(**st, perm_p=p, jackknife_max_p=jkmax, IS_net=stats(isr)["net_pct"],
            OOS_net=stats(oos)["net_pct"], corr_to_v7=corr, placebo_net=plc_net, placebo_p=plc_p, cost=cost,
            gates=dict(perm=g_perm,jk=g_jk,oos=g_oos,indep=g_indep,placebo=g_plac,cost=g_cost),
            gates_passed=f"{passed}/6", grade=grade)
        print(f"\n### {name}  [{grade}] {passed}/6")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p={p}(Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo净{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts=[n for n,r in out["candidates"].items() if r.get("grade")=="ADOPT"]
    print("\n>>> 10年ADOPT(全主要ゲート通過):", adopts if adopts else "なし → 3本目も見送り。v7一本で確定。LEADは要デモ前進検証。")
    out["adopted"]=adopts
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/edge3_meanrev_10y.json") if USE_DRIVE else "research/results/edge3_meanrev_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
