# -*- coding: utf-8 -*-
"""
p2_challenge_mc.py — P2(株価指数 週初ロング バスケット)のチャレンジ動態モンテカルロ。

P1のv7と同じ思想(docs/16 §3): FundedNextは時間無制限ゆえ「低DDの正エッジ」は
+8%到達 vs −10%失格 の競争で単調有利。週次バスケットリターンを4週ブロックで
最大520週(10年)復元抽出し、レバL(総リスク予算)ごとに Phase1 を判定。
→ p95 maxDD を −10%枠の十分内側に収めるLを採用(G9: −10%枠適合)。

入力: research_backtester / p2_edge_search 経由の US500/NAS100/GER40 月曜LONG 週次(等加重,実コスト後)。
出力: research/results/p2_challenge_mc.json。シミュレーションであり将来約定を保証しない。
"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_portfolio_validate as V

HERE=os.path.dirname(os.path.abspath(__file__))
CORE=["US500","NAS100","GER40"]
SEED=20260608
TARGET=0.08            # Phase1 +8%
FLOOR=-0.10            # 最大DD −10%(静的)
N_PATHS=4000
BLOCK=4                # 4週ブロックブートストラップ(自己相関保持)
MAX_WEEKS=520          # 10年上限

def phase1(weekly_scaled, rng):
    """ブロックブートストラップで Phase1 を1パス判定。戻り: (passed, dq, maxDD, weeks)。"""
    n=len(weekly_scaled); eq=1.0; peak=1.0; mdd=0.0
    w=0
    while w<MAX_WEEKS:
        start=rng.integers(0,n-BLOCK) if n>BLOCK else 0
        block=weekly_scaled[start:start+BLOCK]
        for r in block:
            eq*=(1+r); peak=max(peak,eq); dd=eq/peak-1.0; mdd=min(mdd,dd)
            w+=1
            if eq-1.0<=FLOOR or dd<=FLOOR:  # 静的−10%(初期残高基準)/トレーリング両にらみで保守
                return False,True,mdd,w
            if eq-1.0>=TARGET:
                return True,False,mdd,w
            if w>=MAX_WEEKS: break
    return False,False,mdd,w

def run():
    Bmon=V.basket_weekly(CORE).values    # 生(等加重)週次リターン
    raw_std=float(np.std(Bmon)); raw_mean=float(np.mean(Bmon))
    print(f"バスケット週次: n={len(Bmon)} mean={raw_mean*100:.3f}% std={raw_std*100:.3f}% "
          f"年率(複利)={((1+raw_mean)**52-1)*100:.2f}%")
    rng=np.random.default_rng(SEED)
    rows=[]
    for L in [0.5,0.75,1.0,1.25,1.5,2.0,2.5,3.0]:
        scaled=Bmon*L
        npass=ndq=0; mdds=[]; wks=[]
        for _ in range(N_PATHS):
            p,dq,mdd,w=phase1(scaled,rng)
            npass+=p; ndq+=dq; mdds.append(mdd); wks.append(w)
        mdds=np.array(mdds)
        row=dict(L=L, pass_pct=round(100*npass/N_PATHS,1), dq_pct=round(100*ndq/N_PATHS,1),
                 p95_maxDD=round(float(np.percentile(mdds,5))*100,1),     # 悪side(下位5%)
                 med_maxDD=round(float(np.median(mdds))*100,1),
                 med_weeks=int(np.median(wks)), ann_pct=round((((1+raw_mean*L)**52-1)*100),2))
        rows.append(row)
        print(f"  L={L:<4}: 合格{row['pass_pct']:5}% 失格{row['dq_pct']:4}% "
              f"p95DD{row['p95_maxDD']:6}% medDD{row['med_maxDD']:6}% 中央{row['med_weeks']}週 年率{row['ann_pct']}%")
    out=dict(core=CORE, raw_weekly_mean_pct=round(raw_mean*100,4), raw_weekly_std_pct=round(raw_std*100,4),
             target=TARGET, floor=FLOOR, n_paths=N_PATHS, block=BLOCK, sweep=rows)
    with open(os.path.join(HERE,"results","p2_challenge_mc.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    print("\n保存: research/results/p2_challenge_mc.json")
    # G9 推奨: p95DD が −10%の十分内側(<= -7%目安)の最大L
    ok=[r for r in rows if r["p95_maxDD"]>=-7.0]
    rec=max(ok,key=lambda r:r["L"]) if ok else rows[0]
    print(f"\n[G9 推奨] p95 maxDD を −7%以内に保つ最大レバ ≈ L={rec['L']} "
          f"(p95DD {rec['p95_maxDD']}%, 合格{rec['pass_pct']}%, 年率{rec['ann_pct']}%)")
    return out

if __name__=="__main__":
    run()
