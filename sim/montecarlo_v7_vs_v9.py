#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montecarlo_v7_vs_v9.py
======================
v7(24h保有) vs v9(12h同日決済) vs 併用 の【運用案判定】モンテカルロ。

問い: v9(docs/37, 同エッジ・約半分のDD・スワップ不変)が出たので、運用は
  (A) v7単独を維持      … 24h保有・既定予算0.60
  (B) v9へ置換          … 12h保有・低DDゆえ予算を上げられる可能性
  (C) v7+v9を別Magic併走 … 保有長の違う2本で分散(V6相関0.685を踏まえる)
のどれが最良か。Phase1チャレンジ(+8% / 日次-5% / 累積-10%)に対し、
合格率・失格率・中央到達週・p95最悪DD で比較し、最適予算も各案で探索する。

エンジン: 実H1から「月曜 04/06/08/10 UTC × 3円クロス LONG」の週次PnL系列を、
  24h版(v7)と12h版(v9)で別々に作る。予算は週次%で、各週そのショット数で割って配分
  (= colab_v7_multishot / colab_v9_holdcompare と同一の予算配分思想)。
  併用は v7サブPF + v9サブPF を週次で合算(各サブに別予算)。MCはブロック・ブートストラップ。

⚠ データ: 同梱は Yahoo H1 ~2.76年(2023-08〜2026-06)=一方向の円安局面。よって
  【絶対値(合格率/到達週)は楽観側】。本スクリプトの価値は **3案の相対序列** と
  **v9のDD効率がもたらす予算ヘッドルーム**の提示にある。絶対判定は 10年(Dukascopy)で
  USE_DRIVE=True にして再実行すること(colab_v9_holdcompare_10y.py と同じデータ置き場)。
  数値はJSON直読/単一スカラprintで確認(docs/15の表示破損対策)。

使い方: python3 sim/montecarlo_v7_vs_v9.py   (依存: numpy, pandas)
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# === データ設定（10年で回すなら USE_DRIVE=True に） ===
USE_DRIVE      = False
DRIVE_BASE     = "/content/drive/MyDrive/forex_ml"
H1_DIR         = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "data")

PAIRS   = ["EURJPY", "GBPJPY", "USDJPY"]
HOURS   = [4, 6, 8, 10]
WEEKDAY = 0
PIP     = 0.01
COST_PIP= 2.0
V7_HOLD = 24
V9_HOLD = 12
N_PATHS = 6000
MAX_WEEKS = 520          # 10年=時間無制限の上限
BLOCK   = 4
SEED    = 11

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive マウント不可(ローカル?):", e); USE_DRIVE=False

def _resolve(pair):
    c=[]
    if USE_DRIVE:
        b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv"]
    c+=[f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    raise FileNotFoundError(f"{pair}: H1 CSV見つからず {c}")

def load(pair):
    df=pd.read_csv(_resolve(pair))
    tcol=None
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

CACHE={p:load(p) for p in PAIRS}

def shot_returns(pair, hour, hold):
    df=CACHE[pair]; cv=df["close"].values; idx=df.index
    a=np.where((idx.dayofweek==WEEKDAY)&(idx.hour==hour))[0]; a=a[a+hold<len(cv)]
    s=pd.Series((cv[a+hold]-cv[a])/cv[a]-COST_PIP*PIP/cv[a], index=idx[a])
    s.index=s.index.to_period("W"); return s[~s.index.duplicated()]

def build_matrix(hold):
    return pd.DataFrame({f"{p}_{h:02d}":shot_returns(p,h,hold) for p in PAIRS for h in HOURS}).sort_index()

M7=build_matrix(V7_HOLD)   # v7=24h
M9=build_matrix(V9_HOLD)   # v9=12h

def weekly_portfolio(M, weekly_budget):
    """各週、その週に出たショットへ weekly_budget を等配分(=合算エクスポージャ一定)。"""
    out={}
    for wk,row in M.iterrows():
        rs=row.dropna()
        if len(rs)==0: continue
        out[wk]=float((weekly_budget/len(rs)*rs).sum())
    return pd.Series(out).sort_index()

def blend_weekly(b7, b9):
    """v7サブPF(予算b7) + v9サブPF(予算b9) を週次で合算(別Magic併走の近似)。"""
    w7=weekly_portfolio(M7,b7); w9=weekly_portfolio(M9,b9)
    return w7.add(w9, fill_value=0.0).sort_index()

# ---------- 指標 / MC ----------
def net_pct(s): return round(float(((1+pd.Series(s).dropna()).prod()-1)*100),2)
def maxdd_pct(s):
    eq=(1+pd.Series(s).dropna()).cumprod(); peak=eq.cummax()
    return round(float(((eq-peak)/peak).min())*100,2)
def sharpe(s):
    s=pd.Series(s).dropna(); return round(float(s.mean()/s.std()*np.sqrt(52)),2) if s.std()>0 else 0.0

def block_bootstrap(weekly,n_paths=N_PATHS,max_weeks=MAX_WEEKS,block=BLOCK,seed=SEED):
    rng=np.random.default_rng(seed); w=weekly.values; n=len(w)
    if n==0: return np.zeros((n_paths,max_weeks))
    P=np.empty((n_paths,max_weeks))
    for p in range(n_paths):
        seq=[]
        while len(seq)<max_weeks:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:max_weeks]
    return P

def eval_challenge(P,target=0.08,total_dd=0.10,daily_dd=0.05):
    n,T=P.shape; pas=np.zeros(n,bool); fail=np.zeros(n,bool); wks=np.full(n,np.nan); mdd=np.zeros(n)
    for i in range(n):
        eq=1.0; peak=1.0; m=0.0
        for t in range(T):
            eq*=(1+P[i,t])
            if P[i,t]<=-daily_dd: fail[i]=True; break
            peak=max(peak,eq); dd=(eq-peak)/peak; m=min(m,dd)
            if dd<=-total_dd: fail[i]=True; break
            if eq>=1+target: pas[i]=True; wks[i]=t+1; break
        mdd[i]=m
    return dict(pass_rate=round(float(pas.mean())*100,1), fail_rate=round(float(fail.mean())*100,1),
                timeout_rate=round(float((~pas&~fail).mean())*100,1),
                median_weeks=(None if np.all(np.isnan(wks)) else round(float(np.nanmedian(wks)),0)),
                p95_maxDD_pct=round(float(np.percentile(mdd,5))*100,1),
                median_maxDD_pct=round(float(np.percentile(mdd,50))*100,1))

def metrics(weekly, seed=SEED):
    e=eval_challenge(block_bootstrap(weekly,seed=seed))
    e.update(hist_net_pct=net_pct(weekly), hist_maxDD_pct=maxdd_pct(weekly),
             hist_sharpe=sharpe(weekly), weeks=int(len(weekly)))
    return e

def best_budget(make_weekly, budgets, dd_floor=-7.5, fail_cap=2.0):
    """p95最悪DD>=dd_floor かつ 失格率<=fail_cap の範囲で合格率最大(同率は到達速)の予算。"""
    table={}
    for b in budgets:
        w=make_weekly(b); table[f"{b:.2f}"]=metrics(w)
    cand=[(k,v) for k,v in table.items() if v["p95_maxDD_pct"]>=dd_floor and v["fail_rate"]<=fail_cap]
    cand=cand or list(table.items())
    bk,bv=max(cand,key=lambda kv:(kv[1]["pass_rate"], -(kv[1]["median_weeks"] or 9e9)))
    return bk, bv, table

def run():
    R={}
    R["span"]=dict(weeks_v7=int(len(weekly_portfolio(M7,1.0))),
                   weeks_v9=int(len(weekly_portfolio(M9,1.0))),
                   first=str(M9.index.min()), last=str(M9.index.max()),
                   note="同梱2.76年=楽観側。絶対値でなく相対序列とヘッドルームを見る")

    # 週次PnL相関(同予算1.0)
    al=pd.concat([weekly_portfolio(M7,1.0).rename("v7"),
                  weekly_portfolio(M9,1.0).rename("v9")],axis=1).dropna()
    R["weekly_corr_v7_v9"]=round(float(al["v7"].corr(al["v9"])),3) if len(al)>10 else None

    BUD=[0.40,0.60,0.90,1.20,1.50,2.00,2.50,3.00]

    # --- 同一総予算(0.60)での横並び ---
    B=0.60
    R["equal_budget_0.60"]=dict(
        A_v7_only = metrics(weekly_portfolio(M7,B)),
        B_v9_only = metrics(weekly_portfolio(M9,B)),
        C_blend_50_50 = metrics(blend_weekly(B/2, B/2)))

    # --- 各案を「最適予算」にして公平比較 ---
    b7k,b7v,t7 = best_budget(lambda b: weekly_portfolio(M7,b), BUD)
    b9k,b9v,t9 = best_budget(lambda b: weekly_portfolio(M9,b), BUD)
    # 併用は総予算を v7:v9 で配分(保有長分散)。総予算スイープ、内訳は50:50。
    bbk,bbv,tb = best_budget(lambda b: blend_weekly(b/2,b/2), BUD)
    R["optimal_budget"]=dict(
        A_v7_only=dict(budget=b7k, **b7v),
        B_v9_only=dict(budget=b9k, **b9v),
        C_blend_50_50=dict(total_budget=bbk, **bbv))
    R["budget_tables"]=dict(v7=t7, v9=t9, blend=tb)

    # --- v9のヘッドルーム: v7最適予算と同じp95DDを許すと v9はどこまで積めるか ---
    target_dd = b7v["p95_maxDD_pct"]
    head=None
    for b in BUD:
        m=metrics(weekly_portfolio(M9,b))
        if m["p95_maxDD_pct"]>=target_dd: head=(f"{b:.2f}", m)
    R["v9_headroom_at_v7_DD"]=dict(v7_budget=b7k, v7_p95DD=target_dd,
        v9_max_budget_same_DD=(head[0] if head else None),
        v9_metrics=(head[1] if head else None),
        note="同じ最悪DD許容で v9 が積める予算。>v7なら『低DD→高予算→速い到達』が成立")
    return R

if __name__=="__main__":
    R=run()
    print("=== v7(24h) vs v9(12h) vs 併用  Phase1チャレンジMC ===")
    print("span:",R["span"]); print("週次PnL相関 v7–v9:",R["weekly_corr_v7_v9"],"(低いほど併用の分散が効く)")
    eb=R["equal_budget_0.60"]
    print("\n[同一総予算0.60%]")
    for k,lab in [("A_v7_only","A v7単独 "),("B_v9_only","B v9単独 "),("C_blend_50_50","C 併用50:50")]:
        v=eb[k]
        print(f"  {lab}: 合格{v['pass_rate']:5.1f}% 失格{v['fail_rate']:4.1f}% 到達中央{v['median_weeks']}週 "
              f"p95DD{v['p95_maxDD_pct']:6.1f}% | hist net{v['hist_net_pct']:+.1f}% DD{v['hist_maxDD_pct']:.1f}% SR{v['hist_sharpe']}")
    ob=R["optimal_budget"]
    print("\n[各案・最適予算]")
    for k,lab in [("A_v7_only","A v7単独 "),("B_v9_only","B v9単独 "),("C_blend_50_50","C 併用    ")]:
        v=ob[k]; bud=v.get("budget",v.get("total_budget"))
        print(f"  {lab}(予算{bud}): 合格{v['pass_rate']:5.1f}% 失格{v['fail_rate']:4.1f}% 到達中央{v['median_weeks']}週 p95DD{v['p95_maxDD_pct']:6.1f}%")
    h=R["v9_headroom_at_v7_DD"]
    print(f"\n[v9ヘッドルーム] v7最適予算{h['v7_budget']}(p95DD{h['v7_p95DD']}%)と同DD許容で v9は予算{h['v9_max_budget_same_DD']}まで可")
    # 推奨ロジック(相対序列ベース)
    cands={"A_v7_only":ob["A_v7_only"],"B_v9_only":ob["B_v9_only"],"C_blend_50_50":ob["C_blend_50_50"]}
    best=max(cands.items(),key=lambda kv:(kv[1]["pass_rate"], -(kv[1]["median_weeks"] or 9e9), kv[1]["p95_maxDD_pct"]))
    corr=R["weekly_corr_v7_v9"]
    rec=("併用(C): 相関が中程度で分散が効き、合格率/DDが最良" if best[0]=="C_blend_50_50"
         else ("v9置換(B): 低DDで予算ヘッドルームがあり最良。相関%.2fは高めで併用の上乗せ小"%corr if best[0]=="B_v9_only"
               else "v7維持(A): この標本では既存が最良"))
    print(f"\n>>> 相対序列の暫定推奨: {rec}")
    print("    ※絶対値は2.76年で楽観。10年(USE_DRIVE=True)で再確認のこと。")
    try:
        out=os.path.join(os.path.dirname(os.path.abspath(__file__)),"results","montecarlo_v7_vs_v9_results.json")
        os.makedirs(os.path.dirname(out),exist_ok=True)
        with open(out,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",out)
    except Exception as e:
        print("JSON保存スキップ:",e)
