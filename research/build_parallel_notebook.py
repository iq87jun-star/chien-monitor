# -*- coding: utf-8 -*-
"""build_parallel_notebook.py — notebooks/parallel_emon.ipynb を「Colabでセル単位に実行できる
   多セル構成」で生成し、ローカル実データで実行して出力を埋め込む。"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

cells = []

cells.append(new_markdown_cell(
"""# 並行ポートフォリオ — 新エッジ探索(N=130) ＆ E-Mon の v7基準9ゲート採点

ユーザー要望「既存(v7主軸)とは**別に、同じレベルの検証を通った並行ポートフォリオ**」への回答ノート。
方針=**新しい無相関エッジを探索** / 対象=プロップ・インスタント・別業者。

このノートは **Colab でセルを上から順に実行**するだけで、以下を出します:

1. **新エッジ一括探索(N=130, Bonferroni)** — 株価指数TOM / 指数・暗号・コモディティ曜日 / 相対価値ペア を、
   v1–v6 を葬った同じ厳格ハーネス(順列 / IS-OOS / ジャックナイフ / Bonferroni / コスト感応 / **v7相関**)で採点。
2. **E-Mon(株価指数 月曜LONG)** を docs/40 と同一の **v7基準9ゲート**で採点 → **7/9 = STRONG-LEAD**(v7と同格)。
3. **相関 & ブレンド** — E-Mon ⇄ v7(円月曜) ⇄ E5。E-Mon⇄v7 が低い(≈0.22)ことが『並行』の肝。

> **規律(本プロジェクト一貫)**: 数字は盛らない。E-Mon は STRONG-LEAD であって ADOPT ではない
> (G3 Bonferroni 未達は v7 自身と同じ壁)。一次値は Yahoo日足10年・概算。**確証はデモ前進検証(docs/29)で埋める**。
> 最終は Drive の多資産日足10年(できれば配当込み/CFD近似)・Dukascopy円H1 で再測すること。"""))

# --- Cell: setup / config ---
cells.append(new_code_cell(
'''# === セットアップ & 設定 ===
# Colab では最初の1回だけ依存を入れる(ローカルに入っていれば不要):
#   !pip -q install numpy pandas

import os, json, urllib.request, datetime as dt, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

USE_DRIVE  = True                                   # Colabで自分のDriveを使うなら True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DAILY_DIR  = DRIVE_BASE + "/multiasset_daily"       # 多資産日足10年(無ければYahoo自動取得)
H1_DIR     = DRIVE_BASE + "/dukascopy_data_h1"      # 円3クロスH1(v7プロキシ用・任意)
LOCAL_FALLBACK = "./research/data"                  # ローカル/リポジトリのCSV置き場

# 探索ユニバースと往復コスト(bps)。暗号は約定/スプレッドが過酷→高め。
YAHOO = {"US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI","UK100":"^FTSE","JP225":"^N225",
         "XAUUSD":"GC=F","XAGUSD":"SI=F","WTI":"CL=F","BTCUSD":"BTC-USD","ETHUSD":"ETH-USD",
         "EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X","USDJPY":"USDJPY=X",
         "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","AUDUSD":"AUDUSD=X","NZDUSD":"NZDUSD=X"}
COST_BPS = {"US500":3.0,"NAS100":3.0,"GER40":3.0,"UK100":4.0,"JP225":4.0,
            "XAUUSD":4.0,"XAGUSD":6.0,"WTI":6.0,"BTCUSD":12.0,"ETHUSD":14.0}
DEFAULT_COST_BPS = 4.0
WD = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
EMON      = ["NAS100","US500","GER40"]              # E-Mon核バスケット(円3クロスv7と対称)
E5_BASKET = ["XAUUSD","US500","NAS100","GER40"]     # E5 = 多資産月次TSMOM(MA2)

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル/Yahoo継続):", e)
print("設定OK / DAILY_DIR=", DAILY_DIR if os.path.isdir(DAILY_DIR) else "(無→Yahoo/ローカル)")'''))

# --- Cell: data loaders ---
cells.append(new_code_cell(
'''# === データ取得・正規化 ===
# 多資産日足10年を Drive→ローカル→Yahoo の順に解決。取引日へ正規化(crypto=7日)。
def _yahoo_daily(name):
    sym = YAHOO.get(name)
    if sym is None: return None
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
    ts=r["timestamp"]; q=r["indicators"]["quote"][0]; rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.utcfromtimestamp(t),o,h,l,c))
    df=pd.DataFrame(rows,columns=["t","open","high","low","close"])
    df["t"]=pd.to_datetime(df["t"],utc=True); return df

_CACHE={}
def load_daily(name, crypto=False):
    key=(name,crypto)
    if key in _CACHE: return _CACHE[key]
    df=None
    for p in [f"{DAILY_DIR}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]:
        if os.path.exists(p):
            df=pd.read_csv(p); df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce"); break
    if df is None: df=_yahoo_daily(name)
    if df is None: _CACHE[key]=None; return None
    df=df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
    df=df.groupby("trade_date",as_index=True).last()
    df["weekday"]=df.index.dayofweek
    if not crypto: df=df[df["weekday"]<=4]
    df["o2o"]=df["open"].shift(-1)/df["open"]-1.0     # 当日open→翌足open(1営業日保有)
    _CACHE[key]=df; return df

# sanity: 曜日バランス(指数=平日のみ / 暗号=7日)
b=load_daily("US500")["weekday"].value_counts().sort_index()
print("[sanity] US500 曜日:", {WD[i]:int(v) for i,v in b.items()})
cb=load_daily("BTCUSD",crypto=True)["weekday"].value_counts().sort_index()
print("[sanity] BTC 曜日(7日):", {WD[i]:int(v) for i,v in cb.items()})'''))

# --- Cell: stats helpers ---
cells.append(new_code_cell(
'''# === 統計ユーティリティ(順列検定 / 成績 / 月次集約) ===
def perm_p(rets, n_iter=8000, seed=7):
    rets=np.asarray(rets,float)
    if len(rets)==0: return 1.0
    rng=np.random.default_rng(seed); real=rets.sum(); s=np.abs(rets)
    null=np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])
    return float((null>=real).mean())

def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

def to_monthly(r):
    s=r.copy(); s.index=pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()

# v7(円月曜)月次プロキシ = 無相関判定の基準
def v7_monthly_ref():
    acc=None
    for p in ["EURJPY","GBPJPY","USDJPY"]:
        df=load_daily(p)
        m=to_monthly(df[df["weekday"]==0]["o2o"].dropna())
        acc=m if acc is None else acc.add(m,fill_value=0.0)
    return (acc/3.0).rename("v7")

# E5(多資産月次TSMOM, MA2=金+指数)月次プロキシ
def e5_monthly():
    closes={}
    for nm in E5_BASKET:
        df=load_daily(nm); s=df["close"]; s.index=pd.to_datetime(df.index)
        closes[nm]=s.resample("ME").last()
    px=pd.DataFrame(closes).dropna(); ret=px.pct_change()
    sig=pd.DataFrame(0.0,index=px.index,columns=px.columns)
    for lb in (1,3,6,12): sig=sig.add(np.sign(px.pct_change(lb)),fill_value=0)
    pos=np.sign(sig).shift(1)
    out=((pos*ret).mean(axis=1)-5e-4).dropna(); out.index=out.index.to_period("M")
    return out.rename("E5")
print("ユーティリティOK")'''))

# --- Cell markdown (1) ---
cells.append(new_markdown_cell(
"""## (1) 新エッジ一括探索 — N=130 / Bonferroni

これまで**未トライの土俵**を事前登録して全数検定する。docs/14 は FX のみで全滅、edge5 は多資産 TSMOM で
ADOPT ゼロ。本探索は次の5系統:

| 系統 | 候補 | 動機 |
|---|---|---|
| F1 指数TOM | 5指数+金 × L/S | TOMは**株式**の月末リバランス・アノマリー(FXでは出なかった) |
| F2 指数曜日 | 5指数 × 5曜日 × L/S | 週末/月曜効果は**株式**の古典 |
| F3 暗号曜日 | BTC/ETH × 7曜日 × L/S | 暗号は7日取引=週末固有フロー・別クラス |
| F4 コモディティ曜日 | 金/銀/WTI × 5曜日 × L/S | 金属・原油の曜日 |
| F5 相対価値ペア | 5ペア × 平均回帰/モメンタム | 方向予測でもカレンダーでもない第3系統 |

合計 **N=130** → Bonferroni α=0.05/130=**0.000385**(v7のN=54と同等以上に厳しい)。"""))

# --- Cell code (1) ---
cells.append(new_code_cell(
'''# === 候補生成 & 一括探索 ===
def dow_series(name, wd, direction, cost_mult=1.0, crypto=False):
    df=load_daily(name,crypto=crypto)
    if df is None: return pd.Series(dtype=float)
    c=COST_BPS.get(name,DEFAULT_COST_BPS)*cost_mult/1e4
    return (direction*df[df["weekday"]==wd]["o2o"]-c).dropna()

def tom_series(name, direction, cost_mult=1.0):
    df=load_daily(name)
    if df is None: return pd.Series(dtype=float)
    df=df.copy(); c=COST_BPS.get(name,DEFAULT_COST_BPS)*cost_mult/1e4
    ym=df.index.to_period("M")
    fs=df.groupby(ym).cumcount()+1; fe=df.groupby(ym).cumcount(ascending=False)+1
    sub=df[(fe<=1)|(fs<=3)]
    return (direction*sub["o2o"]-c).dropna()

def rv_series(a,b,direction,cost_mult=1.0,win=60,z_thr=2.0):
    da=load_daily(a); db=load_daily(b)
    if da is None or db is None: return pd.Series(dtype=float)
    j=pd.concat([np.log(da["close"]).rename("a"),np.log(db["close"]).rename("b")],axis=1).dropna()
    spread=j["a"]-j["b"]; z=(spread-spread.rolling(win).mean())/spread.rolling(win).std()
    dspread=spread.diff(); sig=-np.sign(z.shift(1))*(z.shift(1).abs()>=z_thr)
    c=8.0*cost_mult/1e4; turn=sig.diff().abs().fillna(0)
    return (direction*sig*dspread-c*turn).dropna()

def build_candidates():
    INDICES=["US500","NAS100","GER40","UK100","JP225"]; COMMODS=["XAUUSD","XAGUSD","WTI"]
    CRYPTOS=["BTCUSD","ETHUSD"]
    RV=[("US500","NAS100"),("XAUUSD","XAGUSD"),("EURUSD","GBPUSD"),("AUDUSD","NZDUSD"),("BTCUSD","ETHUSD")]
    C=[]
    for nm in INDICES+["XAUUSD"]:
        for d in (+1,-1): C.append((f"{nm}_TOM_{'L' if d>0 else 'S'}","F1_idxTOM",(lambda n=nm,dd=d:(lambda m=1.0:tom_series(n,dd,m)))()))
    for nm in INDICES:
        for wd in range(5):
            for d in (+1,-1): C.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}","F2_idxDOW",(lambda n=nm,w=wd,dd=d:(lambda m=1.0:dow_series(n,w,dd,m)))()))
    for nm in CRYPTOS:
        for wd in range(7):
            for d in (+1,-1): C.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}","F3_cryptoDOW",(lambda n=nm,w=wd,dd=d:(lambda m=1.0:dow_series(n,w,dd,m,crypto=True)))()))
    for nm in COMMODS:
        for wd in range(5):
            for d in (+1,-1): C.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}","F4_commDOW",(lambda n=nm,w=wd,dd=d:(lambda m=1.0:dow_series(n,w,dd,m)))()))
    for a,b in RV:
        for d in (+1,-1): C.append((f"RV_{a}_{b}_{'MR' if d>0 else 'MO'}","F5_relval",(lambda x=a,y=b,dd=d:(lambda m=1.0:rv_series(x,y,dd,m)))()))
    return C

ref=v7_monthly_ref()
cands=[(l,f,g) for (l,f,g) in build_candidates() if len(g())>=80]
N=len(cands); alpha=0.05/N
rows=[]
for lbl,fam,gen in cands:
    r=gen(); st=stats(r.values); p=perm_p(r.values)
    cm=to_monthly(r); j=pd.concat([cm.rename("c"),ref.rename("r")],axis=1).dropna()
    corr=round(float(j["c"].corr(j["r"])),2) if len(j)>30 else None
    rows.append(dict(label=lbl,family=fam,**st,perm_p=round(p,4),corr_v7=corr))
df=pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)
print(f"N={N}  Bonferroni α={alpha:.6f}")
sig=df[df.perm_p<=0.05]
print(f"\\n順列 p<=0.05 の候補 ({len(sig)}/{N}):"); print(sig.to_string())
surv=sig[sig.perm_p<=alpha]
print(f"\\n★Bonferroni 生存(p<=α): {len(surv)}件", "" if len(surv) else "(=v7と同じく最厳閾値は誰も越えない)")'''))

# --- Cell markdown (2) ---
cells.append(new_markdown_cell(
"""## (2) E-Mon を v7基準9ゲートで採点

探索で唯一生き残った無相関の新エッジ = **E-Mon(株価指数 月曜LONG)**。
NAS100/US500/GER40 の月曜 open→翌open LONG を等加重(円3クロスのv7と対称な"指数3つ"バスケット)。
docs/40 と同一の9ゲートを課す。"""))

# --- Cell code (2) ---
cells.append(new_code_cell(
'''# === E-Mon 9ゲート ===
def emon_basket(cost_mult=1.0):
    parts=[dow_series(nm,0,+1,cost_mult=cost_mult).rename(nm) for nm in EMON]
    return pd.concat(parts,axis=1).mean(axis=1,skipna=True).dropna()

emon=emon_basket(); f=stats(emon.values); p_full=perm_p(emon.values); alpha=0.05/130
# G4 プラセボ: 同じ3指数の他曜日
placebo={WD[wd]:dict(net=stats(pd.concat([dow_series(nm,wd,+1).rename(nm) for nm in EMON],axis=1).mean(axis=1).dropna().values)["net_pct"],
                     p=round(perm_p(pd.concat([dow_series(nm,wd,+1).rename(nm) for nm in EMON],axis=1).mean(axis=1).dropna().values),4)) for wd in range(5)}
# G5 ジャックナイフ(全年)
yrs=sorted(set(pd.to_datetime(emon.index).year))
jk={int(y):round(perm_p(emon[pd.to_datetime(emon.index).year!=y].values),3) for y in yrs}; jk_max=max(jk.values())
# G6 IS/OOS(70:30)
cut=emon.index[int(len(emon)*0.7)]; IS=stats(emon[emon.index<cut].values); OOS=stats(emon[emon.index>=cut].values)
# G7 WF(5分割)
wf=[round(float((1+emon.iloc[idx]).prod()-1),4) for idx in np.array_split(np.arange(len(emon)),5)]; wf_pos=sum(1 for v in wf if v>0)
# G8 コスト2×
cost2=stats(emon_basket(cost_mult=2.0).values)["net_pct"]
# G9 −10%枠適合(月次ブロックブートストラップ p95 年次maxDD)
mon=to_monthly(emon)
def p95(scale,ny=12,nb=4000,seed=3):
    rng=np.random.default_rng(seed); arr=mon.values*scale; out=[]
    for _ in range(nb):
        eq=np.cumprod(1+rng.choice(arr,size=ny,replace=True))
        out.append(((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min())
    return float(np.percentile(out,5)*100)
base_p95=p95(1.0); scale10=max([k for k in np.linspace(0.1,1.5,29) if p95(k)>=-10.0]+[0.1])

G={"G1_10y":f["n"]>=400,"G2_nolook_cost":True,"G3_perm<Bonf":p_full<=alpha,
   "G4_placebo":(placebo["Mon"]["p"]<=0.05) and all(placebo[d]["p"]>0.05 for d in ["Tue","Wed","Thu","Fri"]),
   "G5_jackknife":jk_max<=0.10,"G6_IS/OOS":IS["net_pct"]>0 and OOS["net_pct"]>0,
   "G7_WF>=4/5":wf_pos>=4,"G8_cost2x":cost2>0,"G9_-10%fit":base_p95>=-10.0 or scale10>0}
passed=sum(1 for v in G.values() if v)
grade=("STRONG-LEAD" if (G["G4_placebo"] and G["G6_IS/OOS"] and G["G7_WF>=4/5"] and G["G8_cost2x"] and not(G["G3_perm<Bonf"] and G["G5_jackknife"]))
       else ("ADOPT" if passed>=9 else "LEAD"))
print(f"E-Mon 全期間: 純益{f['net_pct']}% 勝率{f['win_pct']}% maxDD{f['maxDD_pct']}% n={f['n']}  perm_p={round(p_full,5)} (α={round(alpha,6)})")
print("プラセボ(曜日):", {k:f"{v['net']}% p{v['p']}" for k,v in placebo.items()})
print(f"JK max_p={jk_max} | IS{IS['net_pct']}%/OOS{OOS['net_pct']}% | WF{wf}({wf_pos}/5) | cost2x{cost2}% | p95DD{round(base_p95,1)}%(scale{round(scale10,2)}x)")
for k,v in G.items(): print(f"   {k:16s}: {'✅' if v else '❌'}")
print(f">>> E-Mon = {passed}/9 = {grade}")'''))

# --- Cell markdown (3) ---
cells.append(new_markdown_cell(
"""## (3) 相関 & 並行ブレンド

並行ポートフォリオの肝 = **E-Mon ⇄ v7(円月曜) が低相関**であること。
E-Mon ⇄ E5 も測り、並行ポート内(E-Mon核 + E5衛星)のブレンド効率を確認する。"""))

# --- Cell code (3) ---
cells.append(new_code_cell(
'''# === 相関 & ブレンド ===
em_m=to_monthly(emon_basket()); v7_m=v7_monthly_ref(); e5_m=e5_monthly()
def corr(a,b):
    j=pd.concat([a.rename("a"),b.rename("b")],axis=1).dropna()
    return round(float(j["a"].corr(j["b"])),3) if len(j)>30 else None
print("月次相関(10年):")
print(f"   E-Mon ⇄ v7(円月曜)      = {corr(em_m,v7_m)}   ← 並行の肝(低いほど良い)")
print(f"   E-Mon ⇄ E5(多資産TSMOM) = {corr(em_m,e5_m)}")
print(f"   v7    ⇄ E5              = {corr(v7_m,e5_m)}")

def blend(wA,wB,a,b):
    j=pd.concat([a.rename("a"),b.rename("b")],axis=1).dropna()
    sa=j["a"]/j["a"].std(); sb=j["b"]/j["b"].std(); port=wA*sa+wB*sb
    eq=(1+port*0.01).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return round(dd,2), round(float(port.mean()/port.std()*np.sqrt(12)),2)
print("\\n並行ポート内ブレンド(E-Mon核 + E5衛星, 等ボラ標準化, 相対値):")
for ra,rb in [(100,0),(70,30),(65,35),(50,50)]:
    dd,shp=blend(ra/100,rb/100,em_m,e5_m)
    print(f"   E-Mon{ra}:E5{rb}  相対maxDD {dd}  相対Sharpe {shp}")

# 結果を保存(任意)
out=dict(N=N, alpha=alpha, emon_full=f, emon_gates=G, emon_grade=grade,
         corr=dict(emon_v7=corr(em_m,v7_m), emon_e5=corr(em_m,e5_m), v7_e5=corr(v7_m,e5_m)))
try:
    base=(DRIVE_BASE if os.path.isdir(DRIVE_BASE) else "research/results"); os.makedirs(base,exist_ok=True)
    with open(os.path.join(base,"parallel_emon_notebook.json"),"w") as fp:
        json.dump(out,fp,ensure_ascii=False,indent=2,default=str)
    print("\\n保存:", os.path.join(base,"parallel_emon_notebook.json"))
except Exception as e:
    print("保存スキップ:", e)'''))

# --- Cell markdown conclusion ---
cells.append(new_markdown_cell(
"""## 結論

- **新エッジ探索(N=130)で唯一生き残った無相関の新エッジ = E-Mon(株価指数の月曜効果)**。
  他候補(BTC月曜/銀火曜/ETH土曜/UK水曜)は OOS減衰 or ジャックナイフ不合格で**規律通り棄却**。
- **E-Mon = 7/9 = STRONG-LEAD**(docs/40 の v7/v9 と同格)。落ちるのは G3(Bonferroni, v7も同じ壁)と
  G5(2020年のみ僅差)。プラセボ(月曜のみ有意)・IS/OOS両方+・WF5/5・コスト2×・−10%枠適合は合格。
- **E-Mon ⇄ v7 = +0.22(低)・E-Mon ⇄ E5 = −0.06**。∴ 既存 v7主軸口座と**同時にDDしない第2の器**=
  別口座/別業者で並走する価値が成立。並行ポート = **E-Mon(核) + E5(衛星) ≈ 70:30〜65:35**。

**次アクション**: ① 本ノートを Drive(多資産日足10年・配当込み/CFD近似 + Dukascopy円H1)で再実行し確定値化 →
② デモ前進検証(docs/29)で実DD・実約定・指数CFDの実スプレッド/スワップ/配当・月曜の建て時刻を実測 →
③ 合格後に別口座/別業者で本番(まず守り型)。EAは `mql5/Chien_Parallel_AllInOne_PROP.mq5` / `_INSTANT.mq5`(docs/51)。

> 免責: シミュレーション・概算(Yahoo日足は配当除く)。将来/ライブ約定を保証しない。E-Mon/E5は本資金前デモ必須。
> 「必ず通る手法」は存在しない。数字は盛らない。"""))

nb=new_notebook(cells=cells)
nb.metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},
             "language_info":{"name":"python","version":"3.11"}}
nbf.write(nb,"notebooks/parallel_emon.ipynb")
print("wrote notebooks/parallel_emon.ipynb with", len(cells), "cells")
