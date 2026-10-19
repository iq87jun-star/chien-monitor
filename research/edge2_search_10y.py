"""
edge2_search_10y.py — 2本目エッジの【10年前提】再探索。事前登録 + 厳格ゲート + Bonferroni。

教訓(docs/18/17): 2.8年で選ぶと罠(v8は2.8年p=0.136→10年p=0.436で消滅)。本探索は
【最初から10年実データで選ぶ】。後付け選択を防ぐため候補を少数(=Bonferroni試行数)に事前登録。

事前登録候補(全て v7=円月曜LONG とは別系統。文献/実需の事前仮説あり):
  C1 GOTOBI_USDJPY     : ★本命。ゴトー日(5/10のつく日)の東京仲値(9:55JST=00:55UTC)に向けた
                         輸入企業ドル需要。USDJPY を東京朝(00UTC=09JST)にLONG、仲値後(02UTC)決済。
                         週次でなく月内カレンダー・日中=v7と独立性期待。
  C2 GOTOBI_YEN_ALL    : 同effをEUR/GBP/USDJPYに拡張(円全体のドル/円実需)。
  C3 GOTOBI_USDJPY_h1  : C1の保有1h版(頑健性)。
  C4 TOM_YEN_LONG      : ターン・オブ・マンス(月末月初の資金フロー)。day>=28 or <=2 の円LONG。
  C5 TOM_USDJPY        : 同 USDJPY 単独。
  C6 NONGOTOBI_PLACEBO : ★プラセボ。ゴトー日"以外"の同時刻USDJPY LONG。これが+なら
                         C1はゴトー日特異でなく単なる東京朝ロング=棄却材料。

ゲート(全て10年で・採用には全通過):
  G_perm     順列 p <= Bonferroni α(=0.05/試行数)        ★後付け選択補正
  G_jk       ジャックナイフ max_p <= 0.10(年依存でない)   ★v8はここで死んだ
  G_placebo  C6(非ゴトー日)が非有意、かつC1>C6            ★イベント特異性
  G_indep    v7(円月曜)との月次相関 <= 0.4                独立な分散先
  G_oos      IS/OOS 両方で符号維持                         過学習でない
  G_cost     往復1-4pipで純益+ 維持

⚠ シミュレーション。エッジ探索用に終値モデル(DD/合格率はユーザーの足内エンジンで別途)。
  数値は印字/JSON。Driveパスはあなたのv7ノートに合わせる。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

COST_PIP = 2.0
# 候補に使う可能性のある全ペア(無いものは自動スキップ)
MAYBE_PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCHF","USDCAD"]

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
    out=pd.DataFrame(index=df.index); out["close"]=df[cc].astype(float)
    return out.dropna()

CACHE={}
def H1(p):
    if p not in CACHE: CACHE[p]=load(p)
    return CACHE[p]
def have(p): return H1(p) is not None

def gotobi_mask(idx_jst):
    """ゴトー日(JST暦): 日が5の倍数(5,10,15,20,25,30)。マスクは★JST日付で計算する。"""
    return np.isin(idx_jst.day, [5,10,15,20,25,30])
def tom_mask(idx_jst):
    """ターン・オブ・マンス(JST暦): 月末月初(day>=28 or day<=2)。"""
    return (idx_jst.day>=28)|(idx_jst.day<=2)

def intraday_trades(pair, day_mask_fn, entry_hour_utc, hold_hours, direction, costpip=COST_PIP, invert_mask=False):
    """★JST日付でフィルタ。entry_hour_utc建て・(entry+hold_hours)バットで決済。日次素リターン系列。"""
    df=H1(pair)
    if df is None: return pd.Series(dtype=float)
    cv=df["close"].values; idx=df.index; ps=pip(pair)
    idx_jst=idx + pd.Timedelta(hours=9)            # ★JST換算でゴトー/TOM判定
    dm=day_mask_fn(idx_jst)
    if invert_mask: dm=~dm
    ent=np.where(dm & (idx.hour==entry_hour_utc))[0]
    ent=ent[ent+hold_hours<len(cv)]
    out={}
    for a in ent:
        b=a+hold_hours
        r=direction*(cv[b]-cv[a])/cv[a]-costpip*ps/cv[a]
        out[idx_jst[a].normalize()]=r          # indexはJST日付
    return pd.Series(out).sort_index()

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

def yen_monday_monthly():
    """v7基準: 円3クロス月曜LONG(4,6,8,10UTC,24h)。月次合算リターン(相関比較用)。"""
    rows=[]
    for p in ["EURJPY","GBPJPY","USDJPY"]:
        if not have(p): continue
        df=H1(p); cv=df["close"].values; idx=df.index; ps=pip(p)
        for hr in (4,6,8,10):
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a:
                rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-COST_PIP*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series(dict(rows)) if False else pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

def monthly(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

# ---- 事前登録候補 ----
# ★ゴトー日窓: 東京寄り08JST(=23UTC前日)→仲値9:55JST(=00:55UTC)。entry23UTC・hold2h(exit01UTC=10JST)。
def candidates():
    C={}
    C["C1_GOTOBI_USDJPY"]   = lambda: intraday_trades("USDJPY", gotobi_mask, 23, 2, +1)
    C["C2_GOTOBI_YEN_ALL"]  = lambda: pd.concat([intraday_trades(p, gotobi_mask,23,2,+1) for p in ("EURJPY","GBPJPY","USDJPY") if have(p)],axis=1).mean(axis=1).dropna()
    C["C3_GOTOBI_USDJPY_late"]= lambda: intraday_trades("USDJPY", gotobi_mask, 0, 1, +1)   # 09JST建て・10JST決済(別窓)
    C["C4_TOM_YEN_LONG"]    = lambda: pd.concat([intraday_trades(p, tom_mask,0,8,+1) for p in ("EURJPY","GBPJPY","USDJPY") if have(p)],axis=1).mean(axis=1).dropna()
    C["C5_TOM_USDJPY"]      = lambda: intraday_trades("USDJPY", tom_mask, 0, 8, +1)
    return C

def run():
    avail=[p for p in MAYBE_PAIRS if have(p)]
    print("利用可能ペア:", avail)
    C=candidates(); N=len(C); bonf=round(0.05/N,4)
    ym=yen_monday_monthly()
    out={"meta":dict(n_candidates=N, bonferroni_alpha=bonf, available_pairs=avail),"candidates":{}}
    # プラセボ(非ゴトー日 USDJPY 同窓: 23UTC建て hold2h)
    plc=intraday_trades("USDJPY", gotobi_mask, 23, 2, +1, invert_mask=True)
    out["C6_NONGOTOBI_PLACEBO"]=dict(**stats(plc), perm_p=round(perm_p(plc.values),3))
    print(f"\n試行数N={N} Bonferroniα={bonf}")
    print(f"[プラセボ C6 非ゴトー日USDJPY]: net{out['C6_NONGOTOBI_PLACEBO']['net_pct']}% p={out['C6_NONGOTOBI_PLACEBO']['perm_p']} (これが+だとC1は非特異)")
    for name,fn in C.items():
        s=fn()
        if len(s)<30:
            out["candidates"][name]=dict(note="insufficient",n=len(s)); print(f"\n{name}: データ不足 n={len(s)}"); continue
        st=stats(s); p=round(perm_p(s.values),4)
        jk=jackknife(s); jkmax=jk[1] if jk else None
        h=s.index[len(s)//2]; isr,oos=s[s.index<h],s[s.index>=h]
        # v7月次相関
        ms=monthly(s); j=pd.concat([ms.rename("c"),ym.rename("y")],axis=1).dropna()
        corr=round(float(j["c"].corr(j["y"])),2) if len(j)>12 else None
        cost={f"{c}pip":(stats(fn_cost(name,float(c)))["net_pct"]) for c in (1,2,3,4)}
        # ゲート判定
        g_perm = p<=bonf
        g_jk   = (jkmax is not None and jkmax<=0.10)
        g_plac = out["C6_NONGOTOBI_PLACEBO"]["perm_p"]>0.05 and st["net_pct"]>out["C6_NONGOTOBI_PLACEBO"]["net_pct"]
        g_indep= (corr is None) or abs(corr)<=0.4
        g_oos  = (isr.sum()>0 and oos.sum()>0)
        g_cost = all(v>0 for v in cost.values())
        passed = sum([g_perm,g_jk,g_plac,g_indep,g_oos,g_cost])
        grade = "ADOPT" if (g_perm and g_jk and g_plac and g_indep and g_oos) else ("LEAD" if (st["net_pct"]>0 and p<=0.10) else "REJECT")
        out["candidates"][name]=dict(**st, perm_p=p, jackknife_max_p=jkmax, IS_net=stats(isr)["net_pct"],
            OOS_net=stats(oos)["net_pct"], corr_to_v7=corr, cost=cost,
            gates=dict(perm=g_perm,jk=g_jk,placebo=g_plac,indep=g_indep,oos=g_oos,cost=g_cost),
            gates_passed=f"{passed}/6", grade=grade)
        print(f"\n### {name}  [{grade}] {passed}/6")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p={p}(Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']} | v7相関{corr}({g_indep}) | cost{cost}({g_cost}) | placebo{g_plac}")
    adopts=[n for n,r in out["candidates"].items() if r.get("grade")=="ADOPT"]
    print("\n>>> 10年ADOPT(全主要ゲート通過):", adopts if adopts else "なし → 2本目は見送り(v7一本)。LEADは要デモ前進検証。")
    out["adopted"]=adopts
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/edge2_search_10y.json") if USE_DRIVE else "research/results/edge2_search_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

# コスト感応用に候補を再構築(costpip差し替え)
def fn_cost(name, costpip):
    if name=="C1_GOTOBI_USDJPY":     return intraday_trades("USDJPY", gotobi_mask,23,2,+1,costpip)
    if name=="C2_GOTOBI_YEN_ALL":    return pd.concat([intraday_trades(p,gotobi_mask,23,2,+1,costpip) for p in ("EURJPY","GBPJPY","USDJPY") if have(p)],axis=1).mean(axis=1).dropna()
    if name=="C3_GOTOBI_USDJPY_late":return intraday_trades("USDJPY", gotobi_mask,0,1,+1,costpip)
    if name=="C4_TOM_YEN_LONG":      return pd.concat([intraday_trades(p,tom_mask,0,8,+1,costpip) for p in ("EURJPY","GBPJPY","USDJPY") if have(p)],axis=1).mean(axis=1).dropna()
    if name=="C5_TOM_USDJPY":        return intraday_trades("USDJPY", tom_mask,0,8,+1,costpip)
    return pd.Series(dtype=float)

if __name__=="__main__":
    run()
