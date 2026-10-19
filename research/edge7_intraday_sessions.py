# -*- coding: utf-8 -*-
"""
edge7_intraday_sessions.py — 未踏フロンティア「イントラデイ・セッション構造」探索(事前登録)。

背景: docs/27/28 で edge7(足内セッション構造)は「10年H1が要る」ため deferred=未探索のまま。
  本スクリプトはその空白を埋める。月曜エッジ(v7)とは別の、セッション(東京/ロンドン/NY/重複)の
  **同日内ドリフト**に方向性のエッジがあるかを、v6/v7と同じ厳格さ＋Bonferroniで検定する。

設計(ノールックアヘッド・同日完結=オーバーナイト無):
  各セッションを (entry_h, exit_h) UTC で定義。全営業日、entry_h の H1始値で建て、exit_h の始値で決済。
  LONG/SHORT 両方向を検定(方向の事後選択をしない)。実コスト往復控除。
  事前登録グリッド = 6セッション × {L,S} × 9ペア = 108 → Bonferroni α=0.05/108。
  循環シフト順列p(自己相関頑健) / IS:OOS(70:30) / ブートストラップ。
  陽性比較対象: 既知のロンドンORB(v3a)は棄却済み=セッション単純ドリフトも大半は死ぬ想定。誇張しない。

⚠ データ: Yahoo H1 ~2.76年=LEAD級スクリーニング。ADOPTには10年H1(Dukascopy)必須(docs/18)。
"""
import os, csv, json, datetime as dt
import numpy as np

HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,"data"); RES=os.path.join(HERE,"results")
os.makedirs(RES,exist_ok=True)
PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
SPREAD_PIPS={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,"USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
SLIP=0.5
# (name, entry_h, exit_h) UTC ・同日内
SESSIONS=[("Tokyo",0,8),("London",7,16),("NY",13,21),("LDN_NY_ovlp",13,16),("Tokyo_open",0,3),("London_open",7,11)]

def pipsz(p): return 0.01 if p.endswith("JPY") else 0.0001
def load_h1(p):
    T=[];O=[]
    with open(os.path.join(DATA,f"{p}_h1.csv")) as f:
        for r in csv.DictReader(f):
            T.append(dt.datetime.fromisoformat(r["timestamp"])); O.append(float(r["open"]))
    return np.array(T,dtype=object), np.array(O,float)
def costfrac(p,px): return (SPREAD_PIPS.get(p,1.5)+2*SLIP)*pipsz(p)/px

def index_pairs(T, entry_h, exit_h):
    """各営業日 entry_h と exit_h(同日,exit>entry) の位置ペアを一度だけ抽出(ベクトル化用)。"""
    byday={}
    for i,t in enumerate(T):
        byday.setdefault(t.date(),{})[t.hour]=i
    ei=[]; xi=[]
    for hrs in byday.values():
        if entry_h in hrs and exit_h in hrs and hrs[exit_h]>hrs[entry_h]:
            ei.append(hrs[entry_h]); xi.append(hrs[exit_h])
    return np.array(ei,int), np.array(xi,int)

def rets_from_pairs(O, ei, xi, p, direction):
    if len(ei)==0: return np.array([])
    e=O[ei]; x=O[xi]
    return direction*(x-e)/e - costfrac(p, e)   # costfrac はベクトル化(px が配列でも可)

def perm_circular(O, ei, xi, p, direction, nperm=3000, seed=7):
    obs=rets_from_pairs(O,ei,xi,p,direction)
    if len(obs)<10: return float("nan"),0
    om=obs.mean(); rng=np.random.default_rng(seed); n=len(O); cnt=0
    idx_e=ei; idx_x=xi
    for _ in range(nperm):
        sh=rng.integers(1,n-1)
        e=O[(idx_e-sh)%n]; x=O[(idx_x-sh)%n]
        pr=direction*(x-e)/e - costfrac(p,e)
        if pr.mean()>=om: cnt+=1
    return cnt/nperm, len(obs)

def maxdd(R):
    eq=np.cumsum(R); pk=np.maximum.accumulate(eq); return float((eq-pk).min()) if len(R) else 0.0

def main():
    data={p:load_h1(p) for p in PAIRS}
    T0=data["EURUSD"][0][0]; T1=data["EURUSD"][0][-1]
    grid=[(p,s,d) for p in PAIRS for s in SESSIONS for d in(+1,-1)]
    N=len(grid); bonf=0.05/N
    print("="*72); print(f"edge7 イントラデイ・セッション構造 探索 | {T0}..{T1}")
    print(f"事前登録 N={N} → Bonferroni α={bonf:.5f}  ⚠H1~2.76年=LEAD級(10年追認必須)"); print("="*72)
    pairs_idx={(p,sname):index_pairs(data[p][0],eh,xh) for p in PAIRS for (sname,eh,xh) in SESSIONS}
    rows=[]
    for (p,(sname,eh,xh),d) in grid:
        T,O=data[p]; ei,xi=pairs_idx[(p,sname)]; R=rets_from_pairs(O,ei,xi,p,d)
        if len(R)<10: continue
        pp,n=perm_circular(O,ei,xi,p,d)
        k=int(len(R)*0.7)
        rows.append(dict(pair=p,session=sname,dir=("L"if d>0 else"S"),n=n,
            mean_bps=round(R.mean()*1e4,2),net=round(R.sum()*100,2),wr=round(float((R>0).mean()),3),
            dd=round(maxdd(R)*100,2),IS=round(R[:k].mean()*1e4,2),OOS=round(R[k:].mean()*1e4,2),perm_p=round(pp,4)))
    rows.sort(key=lambda r:r["perm_p"])
    print(f"\n--- 上位(perm_p昇順, 全{len(rows)}件中) ---")
    for r in rows[:18]:
        surv=r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS"]>0
        print(f"{r['pair']:7s} {r['session']:12s}{r['dir']} n={r['n']:4d} mean={r['mean_bps']:+6.2f}bps "
              f"net={r['net']:+7.2f}% wr={r['wr']:.2f} DD={r['dd']:6.2f}% OOS={r['OOS']:+6.2f} "
              f"perm_p={r['perm_p']:.4f}{'  <==SURVIVE' if surv else ''}")
    surv=[r for r in rows if r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS"]>0]
    print(f"\n=== Bonferroni(α={bonf:.5f})生存: {len(surv)} ===")
    for r in surv: print(f"  {r['pair']} {r['session']}{r['dir']} perm_p={r['perm_p']:.4f} mean={r['mean_bps']:+.2f}bps")
    if not surv: print("  生存ゼロ — セッション単純ドリフトに新エッジ無し（v3a ORB棄却と整合）。")
    json.dump({"span":[str(T0),str(T1)],"N":N,"bonf":bonf,"rows":rows,"survivors":surv},
              open(os.path.join(RES,"edge7_intraday_sessions.json"),"w"),ensure_ascii=False,indent=1,default=str)
    print("\n保存: research/results/edge7_intraday_sessions.json")

if __name__=="__main__":
    main()
