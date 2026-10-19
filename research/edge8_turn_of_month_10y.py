# -*- coding: utf-8 -*-
"""
edge8_turn_of_month_10y.py
==========================
4本目エッジ探索（事前登録）— カレンダー・フロー系シーズナリティ。

動機: 本プロジェクトで唯一生き残った検証済みエッジは「月曜LONG(JPYクロス)」(docs/12,18)。
docs/27 の未踏6候補(E1-E6)に **ターン・オブ・マンス(月末月初, TOM)** は含まれず、未トライ。
TOM は学術的に頑健（株価指数・FXの月末リバランス/フィキシング・フロー）で、保有数日・DD小と
プロップ制約に適合する。月曜効果(曜日構造)とは別の時間構造のため、低相関の2本目シーズナル候補に
なり得る。本スクリプトは v6 と同じ厳格さで、TOM を含むカレンダー仮説を **事前登録グリッド** で
一括検定し、多重検定補正(Bonferroni)後に生き残るものだけを ADOPT 候補とする。

規律(誇張しない):
  - ノールックアヘッド: カレンダー(曜日/月内日)は将来価格を使わず確定。約定は当日始値、決済は保有後の始値。
  - 実コスト: 往復 = spread + 2*slippage(pips) を価格%換算で控除。
  - 評価: 全期間 / IS:OOS(70:30) / ブートストラップ P(mean<=0) / 循環シフト順列p(自己相関頑健)。
  - 多重補正: 事前登録した全 (pair × effect × direction) 本数で Bonferroni。
  - 出なければ「出ない」と書く。本物だけ EA 化する。

データ: research/data/{pair}_d.csv (日足~10年, Yahoo)。最終判定はユーザーのDukascopy/MT5で。
"""
import os, csv, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY_CROSS = ["EURJPY","GBPJPY","USDJPY"]

SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFAULT_SPREAD = 1.5
SLIPPAGE_PIPS = 0.5

def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001

def load_daily(pair):
    path = os.path.join(DATA, f"{pair}_d.csv")
    ts=[]; o=[]; h=[]; l=[]; c=[]
    with open(path) as f:
        for row in csv.DictReader(f):
            ts.append(row["timestamp"][:10])
            o.append(float(row["open"])); h.append(float(row["high"]))
            l.append(float(row["low"]));  c.append(float(row["close"]))
    import datetime as dt
    days = np.array([dt.date.fromisoformat(t) for t in ts])
    return days, np.array(o), np.array(h), np.array(l), np.array(c)

def cost_frac(pair, price_ref):
    """往復コストを価格%（=リターン単位）で。half は片道。"""
    pip = pip_size(pair)
    rt_pips = SPREAD_PIPS.get(pair, DEFAULT_SPREAD) + 2*SLIPPAGE_PIPS
    return (rt_pips * pip) / price_ref

# ---------- カレンダー・マスク ----------
def weekday_mask(days, wd):
    return np.array([d.weekday()==wd for d in days])  # Monday=0

def tom_mask(days, pre=1, post=3):
    """月末 pre 営業日 + 月初 post 営業日 を True。営業日=データに存在する日（FX平日）。"""
    n=len(days); mask=np.zeros(n, bool)
    months=np.array([d.year*12+d.month for d in days])
    # 各月の境界: 月が変わる位置
    for i in range(n):
        # 月初 post 日: i が、その月の先頭から数えて < post なら True
        # 月末 pre 日: i が、その月の末尾から数えて < pre なら True
        m=months[i]
        # 月内での順位
        same=np.where(months==m)[0]
        pos=np.where(same==i)[0][0]
        if pos < post:               # 月初 post 営業日
            mask[i]=True
        if pos >= len(same)-pre:      # 月末 pre 営業日
            mask[i]=True
    return mask

# ---------- 戦略リターン: マスク日に建て hold 日後の始値で決済 ----------
def strat_returns(o, mask, direction, hold, pair):
    """mask[i]=Trueなら i本目始値で建て、i+hold本目始値で決済。重複建ては許可(各シグナル独立)。
       direction: +1 LONG / -1 SHORT。戻り: 各トレードの実コスト後リターン(価格%)。"""
    n=len(o); R=[]
    for i in range(n-hold):
        if not mask[i]: continue
        entry=o[i]; exit_=o[i+hold]
        gross=direction*(exit_-entry)/entry
        R.append(gross - cost_frac(pair, entry))
    return np.array(R, float)

# ---------- 統計 ----------
def boot_p_mean_le0(R, n_boot=5000, seed=42):
    if len(R)<10: return float("nan")
    rng=np.random.default_rng(seed); n=len(R); cnt=0
    for _ in range(n_boot):
        if rng_mean(R, rng, n)<=0: cnt+=1
    return cnt/n_boot

def rng_mean(R, rng, n):
    return R[rng.integers(0,n,n)].mean()

def perm_p_circular(o, mask, direction, hold, pair, n_perm=2000, seed=7):
    """循環シフト順列: 価格系列を環状に回し、同じマスクで戦略平均を再計算。
       自己相関を保持したままカレンダー整合の有意性を検定。p=frac(perm_mean>=obs)。"""
    obs=strat_returns(o, mask, direction, hold, pair)
    if len(obs)<10: return float("nan"), len(obs)
    obs_mean=obs.mean()
    rng=np.random.default_rng(seed); n=len(o); cnt=0
    idx=np.arange(n)
    for _ in range(n_perm):
        sh=rng.integers(1, n-1)
        o_s=o[(idx-sh)%n]
        pr=strat_returns(o_s, mask, direction, hold, pair)
        if len(pr)>0 and pr.mean()>=obs_mean: cnt+=1
    return cnt/n_perm, len(obs)

def maxdd_from_R(R):
    eq=np.cumsum(R); peak=np.maximum.accumulate(eq)
    return float((eq-peak).min()) if len(R) else 0.0

def summarize(o, mask, direction, hold, pair, label):
    R=strat_returns(o, mask, direction, hold, pair)
    n=len(R)
    if n<10: return {"label":label,"pair":pair,"n":n,"note":"too few"}
    k=int(n*0.7); IS=R[:k]; OOS=R[k:]
    pp, _=perm_p_circular(o, mask, direction, hold, pair)
    return {
        "label":label, "pair":pair, "dir":int(direction), "hold":hold, "n":n,
        "mean_bps":round(R.mean()*1e4,3), "net_pct":round(R.sum()*100,2),
        "win_rate":round(float((R>0).mean()),3), "maxDD_pct":round(maxdd_from_R(R)*100,2),
        "IS_mean_bps":round(IS.mean()*1e4,3), "OOS_mean_bps":round(OOS.mean()*1e4,3),
        "boot_P_mean<=0":round(boot_p_mean_le0(R),4), "perm_p":round(pp,4),
    }

def main():
    data={p:load_daily(p) for p in PAIRS}
    span0=data["EURUSD"][0][0]; span1=data["EURUSD"][0][-1]
    print(f"=== edge8 TOM/calendar search | daily {span0}..{span1} | {len(PAIRS)} pairs ===\n")

    # ---- 事前登録グリッド（Bonferroni母数に計上） ----
    grid=[]   # (pair, effect, direction, hold, mask_fn_key)
    # A) 曜日 LONG/SHORT (hold=1)  — 月曜LONGが陽性コントロール
    for p in PAIRS:
        for wd in range(5):
            grid.append((p, f"DOW{wd}", +1, 1, ("wd",wd)))
            grid.append((p, f"DOW{wd}", -1, 1, ("wd",wd)))
    # B) TOM LONG/SHORT (hold=1, 各TOM日を独立シグナル)
    for p in PAIRS:
        grid.append((p, "TOM", +1, 1, ("tom",None)))
        grid.append((p, "TOM", -1, 1, ("tom",None)))
    N=len(grid)
    bonf=0.05/N
    print(f"pre-registered hypotheses N={N} -> Bonferroni alpha={bonf:.5f}\n")

    rows=[]
    for (p, eff, d, hold, mk) in grid:
        days,o,h,l,c=data[p]
        mask = weekday_mask(days, mk[1]) if mk[0]=="wd" else tom_mask(days)
        r=summarize(o, mask, d, hold, p, f"{eff}_{'L' if d>0 else 'S'}")
        r["effect"]=eff
        rows.append(r)

    # ---- 生存者抽出: perm_p < Bonferroni かつ OOS同符号 ----
    survivors=[r for r in rows if isinstance(r.get("perm_p"),float)
               and r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS_mean_bps"]>0]
    survivors.sort(key=lambda r:r["perm_p"])

    print("--- 全グリッド上位(perm_p昇順) ---")
    rows_ok=[r for r in rows if r.get("n",0)>=10]
    for r in sorted(rows_ok, key=lambda r:r["perm_p"])[:18]:
        star="  <== SURVIVE Bonf" if (r["perm_p"]<bonf and r["mean_bps"]>0 and r["OOS_mean_bps"]>0) else ""
        print(f"{r['pair']:7s} {r['label']:8s} n={r['n']:4d} mean={r['mean_bps']:+7.2f}bps "
              f"net={r['net_pct']:+7.2f}% wr={r['win_rate']:.2f} DD={r['maxDD_pct']:6.2f}% "
              f"OOS={r['OOS_mean_bps']:+6.2f} perm_p={r['perm_p']:.4f} boot={r['boot_P_mean<=0']:.3f}{star}")

    # ---- TOM だけを抜き出して俯瞰 ----
    print("\n--- TOM 候補のみ(全ペア, LONG) ---")
    for r in [r for r in rows if r["effect"]=="TOM" and r["dir"]==1]:
        if r.get("n",0)<10: continue
        print(f"{r['pair']:7s} n={r['n']:3d} mean={r['mean_bps']:+7.2f}bps net={r['net_pct']:+6.2f}% "
              f"wr={r['win_rate']:.2f} DD={r['maxDD_pct']:6.2f}% IS={r['IS_mean_bps']:+6.2f} "
              f"OOS={r['OOS_mean_bps']:+6.2f} perm_p={r['perm_p']:.4f}")

    # ---- JPYクロス TOM プール ----
    print("\n--- JPYクロス TOM LONG プール(等加重) ---")
    poolR=[]
    for p in JPY_CROSS:
        days,o,h,l,c=data[p]
        poolR.append(strat_returns(o, tom_mask(days), +1, 1, p))
    poolR=np.concatenate(poolR)
    k=int(len(poolR)*0.7)
    print(f"pooled n={len(poolR)} mean={poolR.mean()*1e4:+.2f}bps net={poolR.sum()*100:+.2f}% "
          f"wr={(poolR>0).mean():.3f} DD={maxdd_from_R(poolR)*100:.2f}% "
          f"IS={poolR[:k].mean()*1e4:+.2f} OOS={poolR[k:].mean()*1e4:+.2f} "
          f"boot_P<=0={boot_p_mean_le0(poolR):.4f}")

    print(f"\n=== SURVIVORS (perm_p<{bonf:.5f}, mean>0, OOS>0): {len(survivors)} ===")
    for r in survivors:
        print(f"  {r['pair']} {r['label']} perm_p={r['perm_p']:.4f} mean={r['mean_bps']:+.2f}bps OOS={r['OOS_mean_bps']:+.2f}")
    if not survivors:
        print("  なし — このグリッドではBonferroni後に生き残る新エッジ無し（月曜含む既知のみ確認）。")

    out={"span":[str(span0),str(span1)], "N_hypotheses":N, "bonferroni_alpha":bonf,
         "rows":rows, "survivors":survivors}
    with open(os.path.join(RESULTS,"edge8_turn_of_month_10y.json"),"w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\nsaved -> results/edge8_turn_of_month_10y.json")

if __name__=="__main__":
    main()
