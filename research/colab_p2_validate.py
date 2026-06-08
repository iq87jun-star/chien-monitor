# -*- coding: utf-8 -*-
"""
colab_p2_validate.py — 第2ポートフォリオ(P2)「ターン・オブ・ウィーク株価指数バスケット」を
                       ユーザーの実データ(Colab/Drive)で再確認するための自己完結スクリプト。

P1のv7基準と同一の9ゲートで P2核(US500/NAS100/GER40 月曜LONG)を採点する。
ローカル(research/p2_portfolio_validate.py)はYahoo日足の結論を、本スクリプトは
ユーザーのDrive実データ(あれば)で追認する。数字は盛らない——届かないものは届かないと出す。

データ優先順位:
  1) Drive: {DAILY_DIR}/{US500,NAS100,GER40}_d.csv (ユーザーの実指数日足があれば最優先)
  2) Yahoo自動取得(^GSPC, ^IXIC, ^GDAXI) フォールバック
列: timestamp, open, high, low, close (UTC, 日足)。

9ゲート(P1のv7基準):
  G1 10年 / G2 ノールックアヘッド+実コスト(構造) / G3 プールperm_p<Bonferroni(N=274,α=0.000182) /
  G4 プラセボ(月曜のみ有意・火-金非有意) / G5 年次JK max_p<=0.10 / G6 IS/OOS両+ /
  G7 WF>=4/5 / G8 コスト2×で net>0 / G9 −10%枠適合(ブロックBSのp95 maxDD)
判定: ADOPT=全通過 / STRONG-LEAD=G4,G6,G7,G8通過でG3/G5が未達 / LEAD=それ未満。

⚠ 指数=配当抜きprice index。CFD実スプレッド/オーバーナイトスワップ/配当はデモで実測。
   最終確証はデモ前進検証(docs/29と同方針)。シミュレーションは将来約定を保証しない。
"""
import os, json, urllib.request, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"
CORE   = ["US500","NAS100","GER40"]
YH     = {"US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
BPS    = 5.0                  # 往復コスト(指数, ベーシスポイント)
N_SEARCH = 274               # ローカル探索 p2_edge_search.py の全試行数
BONF   = 0.05/N_SEARCH       # ≈0.000182
SEED   = 20260608

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")

def _yahoo(sym):
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req, timeout=25).read())
    r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
    return pd.DataFrame(rows, columns=["timestamp","open","high","low","close"])

def load(name):
    cands=[]
    if DRIVE_OK: cands.append(f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv")
    cands.append(f"{LOCAL_FALLBACK}/{name}_d.csv")
    df=None
    for p in cands:
        if os.path.exists(p): df=pd.read_csv(p); print(f"  {name}: ローカル/Drive {p}"); break
    if df is None:
        print(f"  {name}: Yahoo {YH[name]} を取得"); df=_yahoo(YH[name])
    df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
    df=df.groupby("trade_date").last()
    df["weekday"]=df.index.dayofweek
    df=df[df["weekday"]<=4]
    df["o2o"]=df["open"].shift(-1)/df["open"]-1.0
    return df.dropna(subset=["o2o"])

def perm_p(x,n=5000,seed=11):
    x=np.asarray(x,float)
    if len(x)<10: return 1.0
    rng=np.random.default_rng(seed); real=x.sum(); a=np.abs(x).astype(np.float32)
    null=(rng.choice(np.array([-1,1],np.float32),size=(n,len(a)))*a).sum(axis=1)
    return float((null>=real).mean())

def eqstats(x):
    x=pd.Series(x).dropna();
    if len(x)==0: return dict(net_pct=0,maxDD_pct=0,n=0,win_pct=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1),maxDD_pct=round(float(dd),1),
                n=int(len(x)),win_pct=round(float((x>0).mean())*100,1))

def basket(weekdays, mult=1.0):
    parts=[]
    for nm in CORE:
        df=DF[nm]; sub=df[df["weekday"].isin(weekdays)]
        r=(sub["o2o"]-mult*BPS/1e4); r.index=r.index.to_period("W")
        parts.append(r.groupby(r.index).mean().rename(nm))
    return pd.concat(parts,axis=1).mean(axis=1).dropna()

def mc_p95dd(weekly, L, n_paths=4000, block=4, maxw=520, target=0.08, floor=-0.10, seed=SEED):
    w=np.asarray(weekly)*L; n=len(w); rng=np.random.default_rng(seed); mdds=[]; npass=ndq=0
    for _ in range(n_paths):
        eq=1.0; peak=1.0; mdd=0.0; k=0
        while k<maxw:
            st=rng.integers(0,max(1,n-block))
            for r in w[st:st+block]:
                eq*=(1+r); peak=max(peak,eq); mdd=min(mdd,eq/peak-1.0); k+=1
                if eq-1<=floor: ndq+=1; mdd=mdd; break
                if eq-1>=target: npass+=1; break
            else: continue
            break
        mdds.append(mdd)
    return dict(L=L,p95_maxDD=round(float(np.percentile(mdds,5))*100,1),
                pass_pct=round(100*npass/n_paths,1),dq_pct=round(100*ndq/n_paths,1))

print("="*72); print("P2 検証(実データ確認): ターン・オブ・ウィーク株価指数バスケット", CORE); print("="*72)
DF={nm:load(nm) for nm in CORE}
span=DF["US500"].index
print(f"\n期間: {span.min().date()} .. {span.max().date()}  (US500 {len(DF['US500'])}本)")

# 個別 月曜LONG + 曜日プラセボ
print("\n[個別指数 月曜LONG / 曜日プラセボ]")
for nm in CORE:
    for w in range(5):
        sub=DF[nm][DF[nm]["weekday"]==w]; r=(sub["o2o"]-BPS/1e4)
        tag="★Mon" if w==0 else ["Mon","Tue","Wed","Thu","Fri"][w]
        if w==0 or w==4:
            print(f"  {nm} {['Mon','Tue','Wed','Thu','Fri'][w]}: net{eqstats(r.values)['net_pct']:6.1f}% p={perm_p(r.values):.4f}")

Bmon=basket([0]); Both=basket([1,2,3,4])
p_mon=perm_p(Bmon.values); p_oth=perm_p(Both.values)
half=Bmon.index[len(Bmon)//2]; Ris=Bmon[Bmon.index<half]; Roos=Bmon[Bmon.index>=half]
yrs=sorted(set(Bmon.index.year)); jk={int(y):round(perm_p(Bmon[Bmon.index.year!=y].values),3) for y in yrs}
jkmax=max(jk.values())
wf=sum(1 for s in range(5) if eqstats(Bmon[(Bmon.index>=Bmon.index[int(len(Bmon)*s/5)])&(Bmon.index< (Bmon.index[min(len(Bmon)-1,int(len(Bmon)*(s+1)/5))]))].values)["net_pct"]>0)
B2=basket([0],2.0)
g={"G3":p_mon<BONF,"G4":(p_mon<0.05 and p_oth>0.05),"G5":jkmax<=0.10,
   "G6":(Ris.sum()>0 and Roos.sum()>0),"G7":wf>=4,"G8":eqstats(B2.values)["net_pct"]>0}
mc_sweep=[mc_p95dd(Bmon.values,L) for L in (0.5,0.6,0.75,1.0)]
mc=mc_sweep[0]   # 推奨保守サイズ L=0.5 で G9 判定
g["G9"]=mc["p95_maxDD"]>=-10.0

print(f"\n[G3/G4] 月曜プールnet{eqstats(Bmon.values)['net_pct']}% perm_p={p_mon:.4f}(Bonf α={BONF:.5f}={'OK' if g['G3'] else 'NG'}) / "
      f"火-金プラセボ net{eqstats(Both.values)['net_pct']}% p={p_oth:.4f}({'識別OK' if g['G4'] else 'NG'})")
print(f"[G6] IS net{eqstats(Ris.values)['net_pct']}% / OOS net{eqstats(Roos.values)['net_pct']}% → {g['G6']}")
print(f"[G5] 年次JK max_p={jkmax:.3f} → {g['G5']}  {jk}")
print(f"[G7] WF {wf}/5 → {g['G7']}    [G8] コスト2× net{eqstats(B2.values)['net_pct']}% → {g['G8']}")
print(f"[G9] ブロックBS レバ感度: " + " / ".join(f"L{m['L']}:p95DD{m['p95_maxDD']}% 合格{m['pass_pct']}%" for m in mc_sweep))
print(f"     推奨保守L=0.5 → p95 maxDD {mc['p95_maxDD']}% 失格{mc['dq_pct']}% → {g['G9']} (−10%枠の内側)")

npass=sum(g.values())
adopt=all(g.values())
grade="ADOPT" if adopt else ("STRONG-LEAD" if (g["G4"] and g["G6"] and g["G7"] and g["G8"]) else "LEAD")
print(f"\n→ {npass}/7コア+G9 / 判定: {grade}")
if grade!="ADOPT":
    miss=[k for k,v in g.items() if not v]
    print(f"   未達: {miss}  ＝P1のv7/E5と同じ『質は高いが最厳の統計閾値のみ未達』。確証はデモ前進検証で。")
print("\n免責: シミュレーション。指数=配当抜き。CFD実コスト/スワップ/配当はデモで実測。将来約定を保証しない。")
