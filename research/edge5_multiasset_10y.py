"""
edge5_multiasset_10y.py — 多資産(金/株価指数/暗号)トレンド追随を【一括事前登録】10年検定。

経緯: v7(円月曜LONG)が唯一の生存エッジ。FX内の2本目はv8/gotobi/TOM/平均回帰/モメンタム系まで
全滅(docs/14,17,20,21,22)。docs/22の教訓=「時系列モメンタムは"複数資産クラスの分散バスケット"で
こそ機能し、FX単体・近10年は不振」。本バッチはその唯一の未トライ土俵=多資産トレンドを検定する。

データ: Yahoo日足10年(研究用)。XAUUSD(金,GC=F) / US500 / NAS100 / GER40 / BTCUSD / ETHUSD。
        edge4と同じ日次/月次終値モデル。実運用の約定/スプレッドは別途デモで確認。
v7相関は既存FX H1(dukascopy)から円月曜月次を再現して算出。

事前登録6候補(N=6, Bonferroni α=0.05/6=0.0083):
  MA1 TSMOM_BASKET : 多資産バスケット{金,株3指数,BTC,ETH}の時系列モメンタム。各月、過去{1,3,6,12}ヶ月
                     リターン符号の多数決で翌月方向、1ヶ月保有、等加重。★本命(docs/22の本来の土俵)。
  MA2 TSMOM_METALS_IDX : 同 {金,US500,NAS100,GER40}(暗号除外=暗号の支配を排した頑健性)。
  MA3 TSMOM_CRYPTO : 同 {BTC,ETH}単独(暗号トレンドは文献上強い)。
  MA4 XSMOM_BASKET : 横断モメンタム。毎月過去12ヶ月で6資産を順位付け、上位2LONG/下位2SHORT、1ヶ月保有。
  MA5 DONCHIAN_BASKET : 55日ブレイクアウト(タートル流)。終値が55日高値更新でLONG/安値でSHORT、反対まで保有。
  MA6 TSMOM_CROSSCLASS : 多資産バスケット + FX8 を合わせた最広義の分散TSMOM(クラス横断の分散効果を最大化)。
  PLC 各候補に整合プラセボ=同機会でランダム方向(方向シグナルが無価値かの帰無)。

ゲート(全て10年・採用は全主要通過):
  G_perm 順列p<=Bonferroni(0.0083) / G_jk JKmax<=0.10 / G_oos IS・OOS両符号 /
  G_indep v7月次相関<=0.4(できれば負) / G_plac プラセボ非有意かつ候補>プラセボ / G_cost 2-20bpsで+
ADOPT=主要ゲート全通過。1つも無ければ→多資産でも2本目なし=v7一本で確定(誠実な結論)。

⚠ 日次/月次終値モデル・スワップ/品質スプレッド未精緻。指数=price index(配当除く)、金=先物近月。
   採用候補のDD/合格率はユーザー足内エンジンで別途実測し、必ずデモ前進検証を経ること。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"   # 多資産日足の置き場(Drive)。無ければローカルにフォールバック
LOCAL_FALLBACK = "./research/data"

BASE_BPS   = 5.0          # 往復コスト基準(ベーシスポイント)。暗号は2倍で計上
LOOKBACKS  = [1,3,6,12]   # TSMOMルックバック(月)
DON_N      = 55           # Donchianブレイク窓(日)

YEN    = ["EURJPY","GBPJPY","USDJPY"]
MAJORS = ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD"]
FX8    = YEN + MAJORS
METALS_IDX = ["XAUUSD","US500","NAS100","GER40"]
CRYPTO     = ["BTCUSD","ETHUSD"]
BASKET     = METALS_IDX + CRYPTO          # 多資産6
CROSSCLASS = BASKET + FX8                  # クラス横断

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル?):", e); USE_DRIVE=False

def is_fx(a): return a in FX8
def pip(p): return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(name, daily=False):
    c=[]
    if USE_DRIVE:
        if daily:
            b=DAILY_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{name}_d.csv", f"{b}/{name}.csv"]
        else:
            b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{name}_h1.csv", f"{b}/{name}.csv"]
    if daily: c+=[f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:     c+=[f"{LOCAL_FALLBACK}/{name}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None

def _read_close(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE={}
def series(name):
    """FXはH1終値、多資産は日足終値を返す(無ければNone)。"""
    if name not in CACHE:
        p=_resolve(name, daily=not is_fx(name))
        CACHE[name]=_read_close(p) if p else None
    return CACHE[name]
def have(a): return series(a) is not None
def avail(assets): return [a for a in assets if have(a)]

def daily_close(name):
    s=series(name)
    if s is None: return None
    return s.resample("1D").last().dropna() if is_fx(name) else s
def monthly_close(name):
    d=daily_close(name)
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m

def cost_frac(a):
    """往復コスト(価格に対する分数)。FX=2pip/価格相当(月次では極小)、多資産=BASE_BPS、暗号は2倍。"""
    if is_fx(a): return None              # FXは時点別(price依存)で別計算
    bps=BASE_BPS*(2.0 if a in CRYPTO else 1.0)
    return bps/1e4

# ---------- 候補シグナル(randomize=Trueで整合プラセボ:同機会・ランダム方向) ----------
def _legs(legs):
    if not legs: return pd.Series(dtype=float)
    s=pd.Series([v for _,v in legs], index=[t for t,_ in legs])
    return s.groupby(s.index).mean().sort_index()

def tsmom(assets, randomize=False, seed=1, bps=BASE_BPS):
    rng=np.random.default_rng(seed); legs=[]
    for a in avail(assets):
        m=monthly_close(a)
        if m is None or len(m)<max(LOOKBACKS)+3: continue
        comp=sum(np.sign(m.pct_change(L)) for L in LOOKBACKS)
        pos=np.sign(comp); nxt=m.pct_change().shift(-1)
        if is_fx(a): cpr=2.0*pip(a)/m                       # 2pip往復(時点別)
        else:        cpr=pd.Series((bps*(2.0 if a in CRYPTO else 1.0)/1e4), index=m.index)
        for t in m.index[:-1]:
            p0=pos.get(t,0)
            if not np.isfinite(p0) or p0==0: continue
            d=rng.choice([-1,1]) if randomize else p0
            legs.append((t, d*nxt[t]-cpr[t]))
    return _legs(legs)

def xsmom(assets, randomize=False, seed=2, bps=BASE_BPS, k=2):
    rng=np.random.default_rng(seed); ps=avail(assets)
    M=pd.concat({a:monthly_close(a) for a in ps if monthly_close(a) is not None},axis=1).dropna(how="all")
    if M.shape[1]<2*k+1 or len(M)<15: return pd.Series(dtype=float)
    R=M.pct_change(); past=M.pct_change(12); nxt=R.shift(-1)
    cst={}
    for a in M.columns:
        cst[a]=(2.0*pip(a)/M[a]) if is_fx(a) else pd.Series((bps*(2.0 if a in CRYPTO else 1.0)/1e4),index=M.index)
    cost=pd.DataFrame(cst)
    out={}
    for t in M.index[:-1]:
        rk=past.loc[t].dropna()
        if len(rk)<2*k: continue
        if randomize:
            cols=list(rk.index); rng.shuffle(cols); lo,sh=cols[:k],cols[k:2*k]
        else:
            srt=rk.sort_values(); sh=list(srt.index[:k]); lo=list(srt.index[-k:])
        nx=nxt.loc[t]; ct=cost.loc[t]
        r=np.nanmean([nx[c]-ct[c] for c in lo]) - np.nanmean([nx[c]+ct[c] for c in sh])
        if np.isfinite(r): out[t]=r
    return pd.Series(out).sort_index()

def donchian(assets, randomize=False, seed=3, bps=BASE_BPS, n=DON_N):
    rng=np.random.default_rng(seed); cols=[]
    for a in avail(assets):
        d=daily_close(a)
        if d is None or len(d)<n+10: continue
        hi=d.rolling(n).max().shift(1); lo=d.rolling(n).min().shift(1)
        sig=pd.Series(np.where(d>hi,1.0,np.where(d<lo,-1.0,np.nan)),index=d.index)
        if randomize:
            br=sig.dropna().index
            sig=pd.Series(np.nan,index=d.index); sig.loc[br]=rng.choice([-1,1],size=len(br))
        pos=sig.ffill().fillna(0.0)
        dret=d.pct_change()
        cf=(bps*(2.0 if a in CRYPTO else 1.0)/1e4) if not is_fx(a) else (2.0*pip(a)/d.mean())
        gross=pos.shift(1)*dret
        cost=pos.diff().abs()*cf
        cols.append((gross-cost).dropna())
    if not cols: return pd.Series(dtype=float)
    return pd.concat(cols,axis=1).mean(axis=1).dropna()

# ---------- 統計(edge4と同一ハーネス) ----------
def perm_p(r,n=3000,seed=13):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def perm_p_robust(s,n=3000,seed=13):
    """★経路依存系(Donchianは同一建玉を数週間保有→日次リターンが正に自己相関)で順列pが過大評価に
       なるのを是正。月次集約してから符号シャッフル=独立性仮定をブロック単位で満たす保守的p。"""
    s=pd.Series(s).dropna()
    if len(s)==0: return 1.0
    ms=s.groupby(s.index.to_period("M")).sum()
    return perm_p(ms.values,n=n,seed=seed)
def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1),win_pct=round((x>0).mean()*100,0),maxDD_pct=round(dd,1),n=int(len(x)))
def jackknife(s):
    yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    jk={int(y):round(perm_p_robust(s[s.index.year!=y]),3) for y in yrs}  # ★頑健版で年依存を検査
    return jk, round(max(jk.values()),3)
def mP(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

def yen_monday_monthly():
    """v7(円月曜LONG)の月次リターンをFX H1から再現→相関の基準。"""
    rows=[]
    for p in YEN:
        if not have(p): continue
        s=series(p); cv=s.values; idx=s.index; ps=pip(p)
        for hr in (4,6,8,10):
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a: rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

CAND={
 "MA1_TSMOM_BASKET":     lambda b=BASE_BPS: tsmom(BASKET,     bps=b),
 "MA2_TSMOM_METALS_IDX": lambda b=BASE_BPS: tsmom(METALS_IDX, bps=b),
 "MA3_TSMOM_CRYPTO":     lambda b=BASE_BPS: tsmom(CRYPTO,     bps=b),
 "MA4_XSMOM_BASKET":     lambda b=BASE_BPS: xsmom(BASKET,     bps=b),
 "MA5_DONCHIAN_BASKET":  lambda b=BASE_BPS: donchian(BASKET,  bps=b),
 "MA6_TSMOM_CROSSCLASS": lambda b=BASE_BPS: tsmom(CROSSCLASS, bps=b),
}
PLAC={
 "MA1_TSMOM_BASKET":     lambda: tsmom(BASKET,randomize=True),
 "MA2_TSMOM_METALS_IDX": lambda: tsmom(METALS_IDX,randomize=True),
 "MA3_TSMOM_CRYPTO":     lambda: tsmom(CRYPTO,randomize=True),
 "MA4_XSMOM_BASKET":     lambda: xsmom(BASKET,randomize=True),
 "MA5_DONCHIAN_BASKET":  lambda: donchian(BASKET,randomize=True),
 "MA6_TSMOM_CROSSCLASS": lambda: tsmom(CROSSCLASS,randomize=True),
}

def run():
    print("利用可能 多資産:", avail(BASKET), "/ FX(相関用):", avail(FX8))
    N=len(CAND); bonf=round(0.05/N,4); ym=yen_monday_monthly()
    out={"meta":dict(n_candidates=N,bonferroni_alpha=bonf,lookbacks=LOOKBACKS,don_n=DON_N,base_bps=BASE_BPS,
                     available_assets=avail(BASKET)),"candidates":{}}
    print(f"\n試行数N={N} Bonferroniα={bonf} / コスト基準{BASE_BPS}bps(暗号2x) / v7基準月数={len(ym)}")
    for name,fn in CAND.items():
        s=fn()
        if len(s)<30:
            out["candidates"][name]=dict(note="insufficient",n=len(s)); print(f"\n{name}: データ不足 n={len(s)}"); continue
        st=stats(s); p_daily=round(perm_p(s.values),4); p=round(perm_p_robust(s),4)  # ★gateは頑健版p
        jk=jackknife(s); jkmax=jk[1] if jk else None
        h=s.index[len(s)//2]; isr,oos=s[s.index<h],s[s.index>=h]
        j=pd.concat([mP(s).rename("c"),ym.rename("y")],axis=1).dropna()
        corr=round(float(j["c"].corr(j["y"])),2) if len(j)>12 else None
        plc=PLAC[name](); plc_p=round(perm_p_robust(plc),3); plc_net=stats(plc)["net_pct"]
        cost={f"{c}bps":stats(fn(float(c)))["net_pct"] for c in (2,5,10,20)}
        dd_ok=st["maxDD_pct"]>=-10.0                  # プロップ-10%口座で素のサイズが収まるか(参考)
        g_perm=p<=bonf; g_jk=(jkmax is not None and jkmax<=0.10)
        g_oos=(isr.sum()>0 and oos.sum()>0); g_indep=(corr is None) or abs(corr)<=0.4
        g_plac=(plc_p>0.05 and st["net_pct"]>plc_net); g_cost=all(v>0 for v in cost.values())
        passed=sum([g_perm,g_jk,g_oos,g_indep,g_plac,g_cost])
        grade="ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac) else ("LEAD" if (st["net_pct"]>0 and p<=0.10) else "REJECT")
        out["candidates"][name]=dict(**st,perm_p=p,perm_p_daily=p_daily,jackknife_max_p=jkmax,IS_net=stats(isr)["net_pct"],
            OOS_net=stats(oos)["net_pct"],corr_to_v7=corr,placebo_net=plc_net,placebo_p=plc_p,cost=cost,
            dd_within_10pct=dd_ok,
            gates=dict(perm=g_perm,jk=g_jk,oos=g_oos,indep=g_indep,placebo=g_plac,cost=g_cost),
            gates_passed=f"{passed}/6",grade=grade)
        ddnote="" if dd_ok else f" ⚠DD{st['maxDD_pct']}%≫-10%=素サイズはプロップ不可(要大幅縮小+デモ)"
        print(f"\n### {name}  [{grade}] {passed}/6{ddnote}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p頑健={p}(日次{p_daily}/Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts=[n for n,r in out["candidates"].items() if r.get("grade")=="ADOPT"]
    leads=[n for n,r in out["candidates"].items() if r.get("grade")=="LEAD"]
    print("\n>>> 10年ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 多資産トレンドも全滅 → 2本目なし、v7一本で確定。")
    elif adopts:
        print(">>> ADOPT候補あり → デモ前進検証＋足内エンジンでDD/合格率実測へ(本資金は確認後)。")
    out["adopted"]=adopts; out["leads"]=leads
    try:
        path=(DAILY_DIR.format(base=DRIVE_BASE)+"/edge5_multiasset_10y.json") if USE_DRIVE else "research/results/edge5_multiasset_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
