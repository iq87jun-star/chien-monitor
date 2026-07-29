"""
edge24_signal.py — X_MOM 月次シグナルカード(edge24 の運用実行体 / docs/194)。

毎月最初の3営業日以内に1回実行するだけの「月次EA」:
  1. S&P100 の 12-1 モメンタム上位10銘柄(今月の保有)を算出
  2. 前月保有との差分(売り/買い)を提示
  3. 前月シグナルの実測リターン(コスト込)とベンチ超過を自動評価し、累計を更新
  4. 中止基準(docs/194)を自動チェック
記録は Drive(forex_ml/results/edge24_forward_log.json)に永続化。Drive が無ければローカル。

⚠ 前進検証中(3ヶ月)は docs/192 の登録ロジックを一切変更しない。
   本スクリプトの出力に従うだけ。裁量介入した月は記録上「逸脱」として残すこと。
"""
import json, math, os, time, urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

TOP_N=10; COST_RT=0.002; LOOKBACK=12; SKIP=1
STOP_CUM_EXCESS=-0.15          # 中止基準: 累計超過がこれを下回ったら検証中止(失敗として記録)

UNIVERSE=("AAPL ABBV ABT ACN ADBE AIG AMD AMGN AMT AMZN AVGO AXP BA BAC BK BKNG BLK BMY BRK-B C "
"CAT CHTR CL CMCSA COF COP COST CRM CSCO CVS CVX DE DHR DIS DOW DUK EMR ETN F FDX GD GE GILD GM "
"GOOG GS HD HON IBM INTC INTU ISRG JNJ JPM KHC KO LIN LLY LMT LOW MA MCD MDLZ MDT MET META MMM "
"MO MRK MS MSFT NEE NFLX NKE NOW NVDA ORCL PEP PFE PG PM PYPL QCOM RTX SBUX SCHW SO SPG T TGT "
"TMO TMUS TSLA TXN UNH UNP UPS USB V VZ WFC WMT XOM").split()

try:
    if not os.path.exists("/content/drive/MyDrive"):
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
except Exception:
    pass
STATE_DIR = ("/content/drive/MyDrive/forex_ml/results"
             if os.path.exists("/content/drive/MyDrive/forex_ml") else "research/results")
os.makedirs(STATE_DIR, exist_ok=True)
LOG_PATH = os.path.join(STATE_DIR, "edge24_forward_log.json")


def fetch_monthly(sym, retries=2):
    p2=int(time.time()); p1=p2-500*86400          # 直近~16ヶ月で足りる
    u=(f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
       f"?interval=1d&period1={p1}&period2={p2}&events=div%2Csplit")
    for a in range(retries+1):
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=json.loads(urllib.request.urlopen(req,timeout=30).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]
            adj=r["indicators"].get("adjclose",[{}])[0].get("adjclose") \
                or r["indicators"]["quote"][0]["close"]
            s=pd.Series(adj, index=pd.to_datetime(ts,unit="s",utc=True)).dropna()
            return s.resample("ME").last()
        except Exception:
            if a==retries: return None
            time.sleep(1.5)


def build_panel():
    cols={}
    for i,sym in enumerate(UNIVERSE):
        s=fetch_monthly(sym)
        if s is not None: cols[sym]=s
        if (i+1)%25==0: print(f"  取得 {i+1}/{len(UNIVERSE)}")
        time.sleep(0.2)
    px=pd.DataFrame(cols).sort_index()
    # 進行中の月(未完)は落とす: 最終行が月末±3日以内でなければ部分月とみなす
    last=px.index[-1]
    if (last - last.to_period("M").to_timestamp(how="end").tz_localize("UTC")).days < -3:
        px=px.iloc[:-1]
    return px


def picks_at(px, t):
    mom=px.shift(SKIP)/px.shift(LOOKBACK)-1.0
    row=mom.iloc[t].dropna()
    if len(row)<40: raise RuntimeError("有効銘柄が不足")
    return sorted(row.rank(ascending=False).nsmallest(TOP_N).index)


def main():
    print("="*72); print("edge24 X_MOM 月次シグナル(docs/194 運用カード)"); print("="*72)
    px=build_panel()
    asof=f"{px.index[-1]:%Y-%m}"
    picks=picks_at(px, len(px)-1)

    log=json.load(open(LOG_PATH)) if os.path.exists(LOG_PATH) else {"entries":[],"cum_excess":0.0}
    prev=log["entries"][-1] if log["entries"] else None

    # --- 前月シグナルの実測評価 ---
    if prev and prev["asof"] != asof:
        ret=px.pct_change().iloc[-1]                     # 前月末→今月末
        held=[s for s in prev["picks"] if s in ret.index and not math.isnan(ret[s])]
        turn=len(set(picks)-set(prev["picks"]))/TOP_N
        realized=float(np.mean([ret[s] for s in held]))-COST_RT*turn
        bench=float(ret.dropna().mean())
        log["cum_excess"]=float(log["cum_excess"]+(realized-bench))
        prev["realized_net"]=round(realized,4); prev["bench"]=round(bench,4)
        prev["excess"]=round(realized-bench,4)
        print(f"\n[前月 {prev['asof']} の実測] 戦略 {realized*100:+.2f}% / ベンチ {bench*100:+.2f}% "
              f"/ 超過 {(realized-bench)*100:+.2f}% / 累計超過 {log['cum_excess']*100:+.2f}%")

    # --- 中止基準チェック ---
    if log["cum_excess"] <= STOP_CUM_EXCESS:
        print(f"\n🛑 中止基準: 累計超過 {log['cum_excess']*100:.1f}% ≤ {STOP_CUM_EXCESS*100:.0f}% "
              "→ 前進検証を中止し docs/194 に失敗として記録すること")

    # --- 今月の指示 ---
    print(f"\n[今月のシグナル {asof} 月末基準]")
    print("  保有(等ウェイト10銘柄):", " ".join(picks))
    if prev:
        sells=sorted(set(prev["picks"])-set(picks)); buys=sorted(set(picks)-set(prev["picks"]))
        print("  売り:", " ".join(sells) if sells else "なし")
        print("  買い:", " ".join(buys) if buys else "なし")
    else:
        print("  (初回: 10銘柄すべて新規建て)")

    if not prev or prev["asof"] != asof:
        log["entries"].append(dict(asof=asof, picks=picks, ts=time.strftime("%Y-%m-%d")))
    else:
        print("\n(同月内の再実行: 記録は追加しません)")
    with open(LOG_PATH,"w",encoding="utf-8") as f:
        json.dump(log,f,ensure_ascii=False,indent=2)
    n=len(log["entries"])
    print(f"\n記録: {LOG_PATH} (通算{n}ヶ月目/前進検証は3ヶ月で docs/29 準用判定)")


main()
