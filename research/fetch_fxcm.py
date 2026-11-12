# -*- coding: utf-8 -*-
"""FXCM 公開ローソク足アーカイブ(candledata.fxcorporate.com・H1・BID/ASK・週次ファイル)の取得と、Dukascopy 系列への継ぎ足し(docs/244 Q182・docs/422)。
 Dukascopy(data_dukascopy/<SYM>_hour*.csv.gz)は 2026-08 で止まっている(取得制限)。主要通貨ペアの 2026-09 以降を FXCM で補う。
 既定のクライアント名で取得し、1 件ごとに間隔を空ける。保存先 data_fxcm/ は git 管理外(本スクリプトで再取得できる)。
 使い方: cd research && python3 fetch_fxcm.py [年] [開始週] [終了週] [ペア,ペア,...]
 読み込み: from fetch_fxcm import load_fxcm, load_spliced   # load_spliced(sym, ask=False) = Dukascopy 〜 CUT、以降 FXCM"""
import os, sys, io, gzip, time, subprocess
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "data_fxcm"); DUKA = os.path.join(HERE, "data_dukascopy")
CUT = pd.Timestamp("2026-08-31 23:00")          # Dukascopy の最終バー。これより後を FXCM で継ぐ
PAIRS = ["GBPJPY", "AUDJPY", "USDJPY", "EURJPY", "NZDJPY", "CADJPY", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD", "EURGBP", "EURAUD", "EURCHF", "GBPCHF", "AUDCAD", "AUDNZD", "CADCHF", "NZDCAD"]
def _get(sym, year, week):
    raw = subprocess.run(["curl", "-s", "--max-time", "30", f"https://candledata.fxcorporate.com/H1/{sym}/{year}/{week}.csv.gz"], capture_output=True).stdout
    try: d = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    except Exception: return None
    d["timestamp"] = pd.to_datetime(d["DateTime"], format="%m/%d/%Y %H:%M:%S.%f"); return d
def fetch(sym, year, w0, w1, pause=0.2):
    parts = []
    for w in range(w0, w1 + 1):
        d = _get(sym, year, w)
        if d is not None and len(d): parts.append(d)
        time.sleep(pause)
    if not parts: return 0
    d = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp"); os.makedirs(OUT, exist_ok=True)
    for side, suf in (("Bid", ""), ("Ask", "_ask")):
        o = pd.DataFrame({"timestamp": d.timestamp, "open": d[f"{side}Open"], "high": d[f"{side}High"], "low": d[f"{side}Low"], "close": d[f"{side}Close"]})
        o["volume"] = (o.high > o.low).astype(float)                       # FXCM に出来高は無い。値動きのあるバー = 1(既存の「volume > 0」フィルターに合わせる)
        p = os.path.join(OUT, f"{sym}_hour{suf}.csv.gz")
        if os.path.exists(p):
            old = pd.read_csv(p, parse_dates=["timestamp"]); o = pd.concat([old, o]).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
        o.to_csv(p, index=False, compression="gzip")
    return len(d)
def load_fxcm(sym, ask=False):
    return pd.read_csv(os.path.join(OUT, f"{sym}_hour{'_ask' if ask else ''}.csv.gz"), parse_dates=["timestamp"]).set_index("timestamp").sort_index()
def load_duka(sym, ask=False):
    return pd.read_csv(os.path.join(DUKA, f"{sym}_hour{'_ask' if ask else ''}.csv.gz"), parse_dates=["timestamp"]).set_index("timestamp").sort_index()
def load_spliced(sym, ask=False):
    """Dukascopy を CUT まで、以降を FXCM。FXCM に無いペアは Dukascopy のまま返す。"""
    a = load_duka(sym, ask)
    try: b = load_fxcm(sym, ask)
    except FileNotFoundError: return a
    return pd.concat([a[a.index <= CUT], b[b.index > CUT]])
if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026; w0 = int(sys.argv[2]) if len(sys.argv) > 2 else 20; w1 = int(sys.argv[3]) if len(sys.argv) > 3 else 47
    pairs = sys.argv[4].split(",") if len(sys.argv) > 4 else PAIRS
    for s in pairs:
        n = fetch(s, year, w0, w1); print(s, n, flush=True)
