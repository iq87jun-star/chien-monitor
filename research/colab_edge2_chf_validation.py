"""
colab_edge2_chf_validation.py — v8(USDCHF 木曜午後 SHORT)の【10年H1】追認。

背景: v8 は committed 2.8年で「純益+5.6%/DD-3.1%/p=0.136(LEAD)」。だが docs/18 で
v7のDDが2.8年→10年で約3倍に膨らんだ前例があり、v8も同じ罠(しかもLEADゆえ深刻)。
本スクリプトを実10年H1で回し、(1)エッジが本物か、(2)2.8年の好績が楽観でないか を判定する。

ユーザーの v7 検証ノートと同じデータローダ規約(dukascopy_data_h1/{PAIR}_h1.csv, UTC, 実bid/ask)。

判定ゲート(全て10年で):
  G1 曜日プラセボ: 木曜だけ突出・他曜日非有意か(2.8年では木+5.6%他全マイナス)
  G2 時刻局在: 午後12-20に集中か(午前は-)
  G3 順列 p / Bonferroni: 2.8年 p=0.136 が10年で <=0.05 に締まるか
  G4 ジャックナイフ: 2.8年 max_p=0.483(年依存疑い)が10年で解消するか ★最重要
  G5 10年 maxDD: v8単体の真のDD(2.8年-3.1%は楽観か)
  G6 円月曜(v7)との相関 & 合算DD: 真の分散先か(2.8年 相関0.06)
全通過 → v8を衛星として小サイズ採用。崩れたら破棄(docs/14/15の規律)。

⚠ シミュレーション。数値は JSON直読/marker検証。USDCHFスプレッドは広め→コスト感応注意。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

HOLD = 24
COST_PIP = 2.0
PM = [12,13,14,15,16,17,18,20]     # 木曜午後帯(scanで+ pが集中)
YEN_PAIRS = ["EURJPY","GBPJPY","USDJPY"]; YEN_HOURS=[4,6,8,10]
WD = ["Mon","Tue","Wed","Thu","Fri"]

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
    raise FileNotFoundError(f"{pair} not found: {c}")
def load(pair):
    df=pd.read_csv(_resolve(pair)); tcol=None
    for cand in ("time","timestamp","date","datetime","gmt time"):
        m=[c for c in df.columns if c.lower()==cand]
        if m: tcol=m[0]; break
    if tcol is None: tcol=df.columns[0]
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=None
    for n in ("close","bidclose","bid_close","c"):
        for c in df.columns:
            if c.lower()==n: cc=c; break
        if cc: break
    out=pd.DataFrame(index=df.index); out["close"]=df[cc].astype(float)
    return out.dropna()

CACHE={}
def H1(p):
    if p not in CACHE: CACHE[p]=load(p)
    return CACHE[p]

def leg(pair, wd, hour, direction, hold=HOLD, costpip=COST_PIP):
    df=H1(pair); cv=df["close"].values; idx=df.index; ps=pip(pair)
    a=np.where((idx.dayofweek==wd)&(idx.hour==hour))[0]; a=a[a+hold<len(cv)]
    s=pd.Series(direction*(cv[a+hold]-cv[a])/cv[a]-costpip*ps/cv[a], index=idx[a].to_period("W"))
    return s[~s.index.duplicated()]
def basket(legs, costpip=COST_PIP):
    return pd.concat([leg(p,wd,h,d,hold,costpip) for (p,wd,h,d,hold) in legs],axis=1).mean(axis=1).dropna()

def chf_thu(wd=3, costpip=COST_PIP):
    return basket([("USDCHF",wd,h,-1,HOLD) for h in PM], costpip)
def yen_mon():
    return basket([(p,0,h,+1,HOLD) for p in YEN_PAIRS for h in YEN_HOURS])

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

def run():
    R={}
    base=chf_thu()
    R["chosen"]=dict(pair="USDCHF",weekday="Thu",hours=PM,direction="SHORT",
                     **stats(base),perm_p=round(perm_p(base.values),4))
    # G1 曜日プラセボ
    R["G1_weekday_placebo"]={WD[wd]:dict(**stats(chf_thu(wd)),perm_p=round(perm_p(chf_thu(wd).values),3)) for wd in range(5)}
    # G2 時刻局在(木曜・各時刻単独)
    R["G2_hour"]={h:dict(**stats(leg("USDCHF",3,h,-1)),perm_p=round(perm_p(leg("USDCHF",3,h,-1).values),3)) for h in range(24)}
    # G3 順列 + Bonferroni(週後半USDCHFスキャン規模を仮に試行数 24*5=120)
    R["G3_perm"]=dict(p=R["chosen"]["perm_p"], bonferroni_alpha=round(0.05/120,5),
                      survives=bool(R["chosen"]["perm_p"]<=0.05/120))
    # G4 ジャックナイフ ★最重要
    yrs=sorted(set(base.index.year)); jk={int(y):round(perm_p(base[base.index.year!=y].values),3) for y in yrs}
    R["G4_jackknife"]=jk; R["G4_max_p"]=round(max(jk.values()),3)
    # G5 10年maxDD + IS/OOS + コスト
    h=base.index[len(base)//2]
    R["G5_dd_oos"]=dict(maxDD_pct=stats(base)["maxDD_pct"], IS=stats(base[base.index<h]),
                        OOS=stats(base[base.index>=h]), OOS_p=round(perm_p(base[base.index>=h].values),4))
    R["G5_cost"]={f"{c}pip":stats(chf_thu(3,float(c)))["net_pct"] for c in (1,2,3,4)}
    # G6 円月曜相関 + 合算
    ym=yen_mon(); j=pd.concat([base.rename("chf"),ym.rename("yen")],axis=1).dropna()
    R["G6_corr_to_yen"]=round(float(j["chf"].corr(j["yen"])),2) if len(j)>30 else None
    comb=pd.concat([base.rename("chf"),ym.rename("yen")],axis=1).mean(axis=1).dropna()
    R["G6_combined"]=dict(**stats(comb), yen_only_dd=stats(ym)["maxDD_pct"], chf_only_dd=stats(base)["maxDD_pct"])
    return R

if __name__=="__main__":
    R=run()
    c=R["chosen"]
    print(f"=== v8 USDCHF木曜午後SHORT 10年追認(24h, 往復2pip) ===")
    print(f"  純益{c['net_pct']}% 勝率{c['win_pct']}% maxDD{c['maxDD_pct']}% n={c['n']} p={c['perm_p']}")
    print("\n[G1 曜日プラセボ] 木だけ突出ならエッジ:")
    for k,v in R["G1_weekday_placebo"].items(): print(f"   {k}: {v['net_pct']:+}% p={v['perm_p']}")
    print("\n[G2 時刻] 午後集中?:", {h:(R['G2_hour'][h]['net_pct'],R['G2_hour'][h]['perm_p']) for h in (8,10,12,14,16,18,20)})
    print(f"[G3 順列p={R['G3_perm']['p']} Bonferroni生存={R['G3_perm']['survives']}]")
    print(f"[G4 ★ジャックナイフ max_p={R['G4_max_p']} (<=0.05で年依存解消=合格)]")
    g5=R["G5_dd_oos"]; print(f"[G5 10年maxDD={g5['maxDD_pct']}% IS{g5['IS']['net_pct']}/OOS{g5['OOS']['net_pct']}(p{g5['OOS_p']})] cost={R['G5_cost']}")
    print(f"[G6 円相関={R['G6_corr_to_yen']} 合算net{R['G6_combined']['net_pct']}%/DD{R['G6_combined']['maxDD_pct']}% (円単独DD{R['G6_combined']['yen_only_dd']}%)]")
    gates=[R["G1_weekday_placebo"]["Thu"]["perm_p"]<=0.05, R["chosen"]["perm_p"]<=0.05,
           R["G4_max_p"]<=0.05, (R["G6_corr_to_yen"] or 1)<=0.4, R["chosen"]["net_pct"]>0]
    print(f"\n>>> 10年判定: 5ゲート中 {sum(gates)} 通過。", "★v8衛星採用可" if all(gates) else "未達→衛星は極小 or 破棄")
    try:
        out=(H1_DIR.format(base=DRIVE_BASE)+"/v8_chf_validation.json") if USE_DRIVE else "research/results/v8_chf_validation.json"
        os.makedirs(os.path.dirname(out),exist_ok=True)
        with open(out,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",out)
    except Exception as e:
        print("保存スキップ:",e)
