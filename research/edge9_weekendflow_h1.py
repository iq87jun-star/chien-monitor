# -*- coding: utf-8 -*-
"""
edge9_weekendflow_h1.py
=======================
4本目エッジ探索（事前登録・H1足）— 「週末フロー」ファミリーの両側化。

背景: 本プロジェクトで唯一検証済みのエッジは v7「月曜 04-10UTC LONG(JPYクロス)」。源泉仮説は
『週末に蓄積したマクロ・リスクが週明けにJPYクロスへリスクオン/円キャリー需要として出るフロー』。
docs/12 の曜日プラセボは **全3ペアで「月曜+ / 金曜−」** を示したが、**金曜SHORTは一度もEA化/検定
されていない**。同じ週末フロー機構の鏡像(別日・反対方向)なら、月曜LONGと**低相関**の追加ショットに
なり得る(=v7と同機構で本数を増やせる)。本スクリプトはその仮説を v6/v7 と同じ厳格さで H1 検定する。

⚠ データ制約: Yahoo H1 は ~2.76年（17k本）しか取れない。本プロジェクトの規律では **2.8年は
プロトタイプ専用**（docs/18: 2.8年DDは10年の約1/3に過小評価された）。よって本結果は **LEAD 級**の
スクリーニングであり、ADOPT には**ユーザーの10年H1 (Dukascopy)での追認が必須**。誇張しない。

規律:
  - ノールックアヘッド: (曜日,時刻)はカレンダーで確定。約定はそのH1足始値、決済は hold 本後の始値。
  - 実コスト: 往復 = spread + 2*slippage(pips) を価格%換算で控除。
  - 事前登録グリッド: {Mon, Tue(プラセボ), Fri} × {L,S} × 9ペア = 54本 → Bonferroni α=0.05/54。
  - 帯は v7 と同じ {4,6,8,10}UTC 固定（時刻の事後選択をしない）。
  - 循環シフト順列p(自己相関頑健) / IS:OOS(70:30) / ブートストラップ。
  - 陽性コントロール: 月曜LONG(JPY)が出れば harness 健全。

データ: research/data/{pair}_h1.csv (H1 ~2.76y, Yahoo)。最終判定はユーザーのDukascopy 10年で。
"""
import os, csv, json, datetime as dt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY_CROSS = ["EURJPY","GBPJPY","USDJPY"]
BAND_HOURS = [4,6,8,10]          # v7と同帯(時刻の事後選択をしない)
HOLD_BARS  = 24                  # 24h保有

SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFAULT_SPREAD = 1.5
SLIPPAGE_PIPS = 0.5

def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001

def load_h1(pair):
    path = os.path.join(DATA, f"{pair}_h1.csv")
    T=[]; O=[]
    with open(path) as f:
        for row in csv.DictReader(f):
            T.append(dt.datetime.fromisoformat(row["timestamp"]))
            O.append(float(row["open"]))
    return np.array(T, dtype=object), np.array(O, float)

def cost_frac(pair, price_ref):
    pip = pip_size(pair)
    rt_pips = SPREAD_PIPS.get(pair, DEFAULT_SPREAD) + 2*SLIPPAGE_PIPS
    return (rt_pips * pip) / price_ref

def entry_mask(T, weekday, hours):
    """そのH1足の (曜日==weekday) かつ (時刻∈hours) で True。Python weekday: Mon=0..Sun=6。"""
    hs=set(hours)
    return np.array([ (t.weekday()==weekday and t.hour in hs) for t in T ])

def fwd_returns(O, hold, direction, pair):
    """各バー i で建て hold本後始値で決済した実コスト後リターン(価格%)。長さ n-hold。ベクトル化。"""
    a=O[:-hold]; b=O[hold:]
    gross=direction*(b-a)/a
    pip=pip_size(pair); rt=SPREAD_PIPS.get(pair,DEFAULT_SPREAD)+2*SLIPPAGE_PIPS
    return gross - (rt*pip)/a

def strat_returns(O, mask, direction, hold, pair):
    """mask日のリターンのみ抽出（mask は全長、有効域 [0:n-hold] を使用）。"""
    ret=fwd_returns(O, hold, direction, pair)
    return ret[mask[:len(ret)]]

def boot_p_mean_le0(R, n_boot=4000, seed=42):
    if len(R)<10: return float("nan")
    rng=np.random.default_rng(seed); n=len(R); cnt=0
    for _ in range(n_boot):
        if R[rng.integers(0,n,n)].mean()<=0: cnt+=1
    return cnt/n_boot

def perm_p_circular(O, mask, direction, hold, pair, n_perm=5000, seed=7):
    """循環シフト順列(ベクトル化): リターン系列を固定し mask を環状回転 → 平均を比較。
       価格の自己相関を保持したまま「カレンダー整合の有意性」を検定。p=frac(perm>=obs)。"""
    ret=fwd_returns(O, hold, direction, pair); m=mask[:len(ret)]
    obs=ret[m]
    if len(obs)<10: return float("nan")
    obs_mean=obs.mean(); k=int(m.sum())
    rng=np.random.default_rng(seed); L=len(ret); cnt=0
    pos=np.flatnonzero(m)
    for _ in range(n_perm):
        sh=rng.integers(1, L-1)
        rolled=(pos+sh)%L
        if ret[rolled].mean()>=obs_mean: cnt+=1
    return cnt/n_perm

def maxdd(R):
    eq=np.cumsum(R); peak=np.maximum.accumulate(eq)
    return float((eq-peak).min()) if len(R) else 0.0

def summarize(O, mask, direction, hold, pair, label):
    R=strat_returns(O, mask, direction, hold, pair)
    n=len(R)
    if n<10: return {"label":label,"pair":pair,"n":n,"note":"few"}
    k=int(n*0.7)
    return {"label":label,"pair":pair,"dir":int(direction),"n":n,
        "mean_bps":round(R.mean()*1e4,3),"net_pct":round(R.sum()*100,2),
        "win_rate":round(float((R>0).mean()),3),"maxDD_pct":round(maxdd(R)*100,2),
        "IS_mean_bps":round(R[:k].mean()*1e4,3),"OOS_mean_bps":round(R[k:].mean()*1e4,3),
        "boot_P<=0":round(boot_p_mean_le0(R),4),
        "perm_p":round(perm_p_circular(O,mask,direction,hold,pair),4)}

def main():
    data={p:load_h1(p) for p in PAIRS}
    T0=data["EURUSD"][0][0]; T1=data["EURUSD"][0][-1]
    print(f"=== edge9 weekend-flow H1 | {T0} .. {T1} | hold={HOLD_BARS}h band={BAND_HOURS} ===")
    print("⚠ H1=~2.76年 → LEAD級スクリーニング(10年追認必須)\n")

    WD={"Mon":0,"Tue":2,"Fri":4}   # Tue=プラセボ
    grid=[]
    for p in PAIRS:
        for wname,wd in WD.items():
            for d in (+1,-1):
                grid.append((p,wname,wd,d))
    N=len(grid); bonf=0.05/N
    print(f"pre-registered N={N} -> Bonferroni alpha={bonf:.5f}\n")

    rows=[]
    for (p,wname,wd,d) in grid:
        T,O=data[p]
        mask=entry_mask(T,wd,BAND_HOURS)
        r=summarize(O,mask,d,HOLD_BARS,p,f"{wname}_{'L' if d>0 else 'S'}")
        r["wd"]=wname; rows.append(r)

    rows_ok=[r for r in rows if r.get("n",0)>=10]
    print("--- 上位(perm_p昇順) ---")
    for r in sorted(rows_ok,key=lambda r:r["perm_p"])[:20]:
        surv = r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS_mean_bps"]>0
        star="  <==SURVIVE" if surv else ""
        print(f"{r['pair']:7s} {r['label']:6s} n={r['n']:4d} mean={r['mean_bps']:+7.2f}bps "
              f"net={r['net_pct']:+7.2f}% wr={r['win_rate']:.2f} DD={r['maxDD_pct']:6.2f}% "
              f"OOS={r['OOS_mean_bps']:+6.2f} perm_p={r['perm_p']:.4f} boot={r['boot_P<=0']:.3f}{star}")

    # --- 陽性コントロール: 月曜LONG JPYプール ---
    def pool(wname,wd,d):
        R=[]
        for p in JPY_CROSS:
            T,O=data[p]; R.append(strat_returns(O,entry_mask(T,wd,BAND_HOURS),d,HOLD_BARS,p))
        return np.concatenate(R)
    print("\n--- JPYクロス・プール(等加重, band04-10) ---")
    for wname,wd,d,tag in [("Mon",0,+1,"月曜LONG(=v7陽性コントロール)"),
                           ("Fri",4,-1,"金曜SHORT(=新候補/鏡像)"),
                           ("Tue",2,+1,"火曜LONG(プラセボ)")]:
        R=pool(wname,wd,d); k=int(len(R)*0.7)
        print(f"{tag:28s} n={len(R):4d} mean={R.mean()*1e4:+6.2f}bps net={R.sum()*100:+7.2f}% "
              f"wr={(R>0).mean():.3f} DD={maxdd(R)*100:6.2f}% IS={R[:k].mean()*1e4:+6.2f} "
              f"OOS={R[k:].mean()*1e4:+6.2f} boot_P<=0={boot_p_mean_le0(R):.4f}")

    # --- 月曜LONG vs 金曜SHORT の相関(同機構・別日なら低相関を期待) ---
    print("\n--- 月曜LONG と 金曜SHORT の週次PnL相関(JPYプール) ---")
    monR={}; friR={}
    for p in JPY_CROSS:
        T,O=data[p]
        # 週キーで集計
        for (mask,d,store) in [(entry_mask(T,0,BAND_HOURS),+1,monR),(entry_mask(T,4,BAND_HOURS),-1,friR)]:
            n=len(O)
            for i in range(n-HOLD_BARS):
                if not mask[i]: continue
                wk=T[i].isocalendar()[:2]
                store.setdefault(wk,0.0)
                store[wk]+= d*(O[i+HOLD_BARS]-O[i])/O[i]-cost_frac(p,O[i])
    keys=sorted(set(monR)&set(friR))
    if len(keys)>10:
        a=np.array([monR[k] for k in keys]); b=np.array([friR[k] for k in keys])
        print(f"共通週 n={len(keys)} corr(週次PnL)={np.corrcoef(a,b)[0,1]:+.3f} "
              f"(低いほど分散に有効; 同機構別日の独立性)")

    survivors=[r for r in rows_ok if r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS_mean_bps"]>0]
    print(f"\n=== SURVIVORS Bonferroni(p<{bonf:.5f}): {len(survivors)} ===")
    for r in survivors:
        print(f"  {r['pair']} {r['label']} perm_p={r['perm_p']:.4f}")
    if not survivors:
        print("  Bonferroni後の生存なし。下記プール/相関で候補の質を定性評価する。")

    with open(os.path.join(RESULTS,"edge9_weekendflow_h1.json"),"w") as f:
        json.dump({"span":[str(T0),str(T1)],"N":N,"bonf":bonf,"rows":rows}, f, indent=1, default=str)
    print("\nsaved -> results/edge9_weekendflow_h1.json")

if __name__=="__main__":
    main()
