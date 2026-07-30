# -*- coding: utf-8 -*-
"""
recentfit_sweep.py — 直近フィット・トラック(意図的レジームベット)のスリーブ選定
================================================================================
docs/174 プレレジ準拠。正攻法(10年検証)とは別トラック。
「直近12ヶ月で伸びている」ことだけを採用基準にし、長期の頑健性は要求しない。
ただし以下は守る:
  - ノールックアヘッド(確定足シグナル→次バー始値約定)・実コスト計上
  - 選定はFIT窓のみ。HOLDOUT(直近~12週)は「符号が合うか」のサニティにのみ使用
  - REF窓(前年)の成績は採用に使わず正直に併記(レジーム依存度の開示)

窓 (UTC):
  REF     : 2024-08-01 .. 2025-06-30  (参考・開示用)
  FIT     : 2025-07-01 .. 2026-04-30  (選定用 10ヶ月)
  HOLDOUT : 2026-05-01 .. 2026-07-24  (サニティ ~12週)

戦略族(全て既存EA群で実装済みの型):
  A: 曜日×時刻エントリー・kh時間保有 (H1)     … v7/v9系
  B: 日足TSMOM(n日リターン符号)・1日保有       … v5系
  C: 日足RSI逆張り・h日保有                    … v2系

トレードは R 倍数(リスク単位)で記録: R = 純変化率 / (3×ATR14%) を -1 でクリップ
(EA実装 = 3×ATR緊急SL + 時間決済 と一致)。選定指標も R 基準。
出力: research/results/recentfit_sweep.json
"""
import os, csv, json, math, datetime as dt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_recent")
OUTP = os.path.join(HERE, "results", "recentfit_sweep.json")

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
SLIPPAGE_PIPS = 0.5

REF_A, REF_B = "2024-08-01", "2025-06-30"
FIT_A, FIT_B = "2025-07-01", "2026-04-30"
HOL_A, HOL_B = "2026-05-01", "2026-07-24"

SL_ATR_MULT = 3.0   # 緊急SL距離(EAと一致)。R換算の分母。

def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001

def load(pair, tag):
    path = os.path.join(DATA, f"{pair}_{tag}.csv")
    ts=[]; o=[]; h=[]; l=[]; c=[]
    with open(path) as f:
        for row in csv.DictReader(f):
            ts.append(row["timestamp"]); o.append(float(row["open"]))
            h.append(float(row["high"])); l.append(float(row["low"])); c.append(float(row["close"]))
    return np.array(ts), np.array(o,float), np.array(h,float), np.array(l,float), np.array(c,float)

def atr_pct_daily(pair):
    """日足ATR14(%)を日付->値のdictで返す(その日の確定足まで、翌日に使う)。"""
    ts,o,h,l,c = load(pair,"d")
    pc=np.roll(c,1); pc[0]=c[0]
    tr=np.maximum.reduce([h-l, np.abs(h-pc), np.abs(l-pc)])
    atr=np.empty_like(c); atr[0]=tr[0]; a=1.0/14
    for i in range(1,len(c)): atr[i]=a*tr[i]+(1-a)*atr[i-1]
    out={}
    for i in range(len(c)):
        d=ts[i][:10]
        out[d]=atr[i]/c[i]*100.0
    return out, [t[:10] for t in ts]

def atr_lookup(atr_map, dates_sorted, date):
    """dateより前の直近の日足ATR%(ルックアヘッド無し)。"""
    lo, hi = 0, len(dates_sorted)-1; ans=None
    while lo<=hi:
        mid=(lo+hi)//2
        if dates_sorted[mid] < date: ans=dates_sorted[mid]; lo=mid+1
        else: hi=mid-1
    return atr_map.get(ans) if ans else None

def cost_pct(pair, px):
    return (SPREAD_PIPS.get(pair,1.5)+SLIPPAGE_PIPS)*pip_size(pair)/px*100.0

def to_R(trades):
    """trades: list of (date, net_pct, atrpct) -> R倍数配列(-1クリップ=SL)。"""
    return np.array([max(p/(SL_ATR_MULT*a), -1.0) for _,p,a in trades]) if trades else np.array([])

def window(trades, a, b):
    return [t for t in trades if a <= t[0] <= b]

def stats(trades):
    R = to_R(trades)
    if len(R)==0: return {"n":0}
    wins=R[R>0].sum(); loss=-R[R<=0].sum()
    pf = float(wins/loss) if loss>0 else float("inf")
    t = float(R.mean()/ (R.std(ddof=1)/math.sqrt(len(R)))) if len(R)>2 and R.std(ddof=1)>0 else 0.0
    return {"n":int(len(R)), "sumR":round(float(R.sum()),2), "meanR":round(float(R.mean()),4),
            "pf":round(pf,3) if pf!=float("inf") else 99.0, "tstat":round(t,2),
            "win%":round(float((R>0).mean()*100),1)}

# ---------------- 族A: 曜日×時刻×保有(H1) ----------------
def family_A(pair, atr_map, atr_dates):
    ts,o,h,l,c = load(pair,"h1")
    dts=[dt.datetime.strptime(t,"%Y-%m-%d %H:%M:%S") for t in ts]
    n=len(ts); results=[]
    idx_by_time={t:i for i,t in enumerate(ts)}
    for dow in range(5):
        for hour in (0,4,8,12,16):
            entries=[i for i in range(n-1) if dts[i].weekday()==dow and dts[i].hour==hour]
            for hold in (6,12,24):
                for direction in (1,-1):
                    trades=[]
                    for i in entries:
                        t_exit = dts[i]+dt.timedelta(hours=hold)
                        j=i
                        while j<n-1 and dts[j]<t_exit: j+=1
                        if dts[j]<t_exit: continue  # データ末尾
                        px_in, px_out = o[i], o[j]
                        d=ts[i][:10]
                        a=atr_lookup(atr_map, atr_dates, d)
                        if not a: continue
                        net = direction*(px_out-px_in)/px_in*100.0 - cost_pct(pair,px_in)
                        trades.append((d, net, a))
                    results.append(({"family":"A","pair":pair,"dow":dow,"hour":hour,
                                     "hold":hold,"dir":direction}, trades))
    return results

# ---------------- 族B: 日足TSMOM ----------------
def family_B(pair, atr_map, atr_dates):
    ts,o,h,l,c = load(pair,"d")
    n=len(ts); results=[]
    for lb in (3,5,10,20,60):
        for mode in (1,-1):  # 1=順張り -1=逆張り
            trades=[]
            for i in range(lb+1, n-1):
                sig = np.sign(c[i-1]-c[i-1-lb])
                if sig==0: continue
                direction=int(sig)*mode
                d=ts[i][:10]
                a=atr_lookup(atr_map, atr_dates, d)
                if not a: continue
                net = direction*(o[i+1]-o[i])/o[i]*100.0 - cost_pct(pair,o[i])
                trades.append((d, net, a))
            results.append(({"family":"B","pair":pair,"lookback":lb,"mode":mode}, trades))
    return results

# ---------------- 族C: 日足RSI逆張り ----------------
def rsi_w(c, p):
    d=np.diff(c, prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    au=np.empty_like(c); ad=np.empty_like(c); au[0]=up[0]; ad[0]=dn[0]; a=1.0/p
    for i in range(1,len(c)):
        au[i]=a*up[i]+(1-a)*au[i-1]; ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=np.divide(au, np.where(ad==0,np.nan,ad))
    return np.nan_to_num(100-100/(1+rs), nan=50.0)

def family_C(pair, atr_map, atr_dates):
    ts,o,h,l,c = load(pair,"d")
    n=len(ts); results=[]
    for p in (2,14):
        r=rsi_w(c,p)
        for lo,hi in ((10,90),(20,80),(30,70)):
            for hold in (1,3,5):
                trades=[]
                i=p+1
                while i < n-1-hold:
                    direction=0
                    if r[i-1]<lo: direction=1
                    elif r[i-1]>hi: direction=-1
                    if direction:
                        j=min(i+hold, n-1)
                        d=ts[i][:10]
                        a=atr_lookup(atr_map, atr_dates, d)
                        if a:
                            net=direction*(o[j]-o[i])/o[i]*100.0 - cost_pct(pair,o[i])
                            trades.append((d, net, a))
                        i=j  # 同方向連続シグナルの重複建てを避ける
                    else:
                        i+=1
                results.append(({"family":"C","pair":pair,"rsi_p":p,"lo":lo,"hi":hi,"hold":hold}, trades))
    return results

# ---------------- 選定 ----------------
def main():
    all_results=[]
    for pair in PAIRS:
        atr_map, atr_dates = atr_pct_daily(pair)
        all_results += family_A(pair, atr_map, atr_dates)
        all_results += family_B(pair, atr_map, atr_dates)
        all_results += family_C(pair, atr_map, atr_dates)
    print(f"combos tested: {len(all_results)}")

    rows=[]
    for spec, trades in all_results:
        fit = stats(window(trades, FIT_A, FIT_B))
        if fit["n"] < 25:  # 頻度が低すぎるものは実運用に乗らない
            continue
        hol = stats(window(trades, HOL_A, HOL_B))
        ref = stats(window(trades, REF_A, REF_B))
        rows.append({"spec":spec, "fit":fit, "holdout":hol, "ref":ref})

    # FIT基準の一次フィルタ: PF>=1.3, t>=2.0, ホールドアウト合計R>=0(符号サニティ)
    cand=[r for r in rows if r["fit"]["pf"]>=1.3 and r["fit"]["tstat"]>=2.0
          and r["holdout"].get("n",0)>=3 and r["holdout"].get("sumR",0)>0]
    cand.sort(key=lambda r: -r["fit"]["tstat"])

    # ペア×族で重複排除しつつ上位から最大5本
    picked=[]; seen=set()
    for r in cand:
        key=(r["spec"]["pair"], r["spec"]["family"])
        if key in seen: continue
        seen.add(key); picked.append(r)
        if len(picked)>=5: break

    # 相関の粗チェック: 採用スリーブ同士の日次R相関(FIT窓)
    def daily_series(spec):
        for s,t in all_results:
            if s==spec:
                m={}
                for d,p,a in window(t, FIT_A, FIT_B):
                    m[d]=m.get(d,0.0)+max(p/(SL_ATR_MULT*a),-1.0)
                return m
    corr={}
    for i in range(len(picked)):
        for j in range(i+1,len(picked)):
            a=daily_series(picked[i]["spec"]); b=daily_series(picked[j]["spec"])
            days=sorted(set(a)&set(b))
            if len(days)>=8:
                va=np.array([a[d] for d in days]); vb=np.array([b[d] for d in days])
                if va.std()>0 and vb.std()>0:
                    corr[f"{i}-{j}"]=round(float(np.corrcoef(va,vb)[0,1]),2)

    out={"meta":{"windows":{"ref":[REF_A,REF_B],"fit":[FIT_A,FIT_B],"holdout":[HOL_A,HOL_B]},
                 "sl_atr_mult":SL_ATR_MULT, "combos_tested":len(all_results),
                 "passed_filter":len(cand),
                 "note":"選定はFIT窓のみ。REF窓成績は開示用で採用判断に不使用。"
                        "多重検定は意図的に受容(直近フィット・トラックの設計)。"},
         "picked":picked, "picked_corr_fitwindow":corr,
         "top20_by_fit_tstat":[{"spec":r["spec"],"fit":r["fit"],"holdout":r["holdout"],"ref":r["ref"]}
                                for r in cand[:20]]}
    os.makedirs(os.path.dirname(OUTP), exist_ok=True)
    with open(OUTP,"w") as f: json.dump(out,f,ensure_ascii=False,indent=1)
    print(f"passed filter: {len(cand)}  picked: {len(picked)}")
    for r in picked:
        print(" PICK", r["spec"], "FIT", r["fit"], "HOL", r["holdout"], "REF", r["ref"])
    print("corr:", corr)
    print("->", OUTP)

if __name__ == "__main__":
    main()
