# -*- coding: utf-8 -*-
"""Dukascopy datafeed から H1 ローソク(bid / ask)を月単位で取得し data_dukascopy/<SYM>_hour[_ask].csv.gz に変換する(docs/254)。
・レート制限: 1 リクエスト 9 秒間隔(4 秒で 503)。429/503/接続断は待って再試行。
・再開可能: raw キャッシュ data_dukascopy/raw/<code>/<yyyy>-<mm>_<side>.bi5(git 管理外)。
・銘柄ごとに完了したら csv.gz をコミット・push(コンテナ消失に備える)。
使い方: python3 research/tools/dukascopy_fetch.py <side bid|ask> <SYM=CODE,...> [start YYYY-MM] [end YYYY-MM]
"""
import os, sys, time, lzma, struct, gzip, io, subprocess, urllib.request, urllib.error, datetime as dt
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT)
os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Referer": "https://www.dukascopy.com/"}
GAP = 20.0
def scale(code):
    fx = len(code) == 6 and code.isalpha() and not code.startswith(("XAU", "XAG"))
    return 1e3 if (not fx or code.endswith("JPY")) else 1e5
def fetch(url, tries=6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r: return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return 404, b""
            wait = 90 * (k + 1); print(f"  http {e.code} → {wait}s 待機", flush=True); time.sleep(wait)
        except Exception as e:
            wait = 90 * (k + 1); print(f"  {str(e)[:40]} → {wait}s 待機", flush=True); time.sleep(wait)
    return 0, b""
def decode(data, code, y, m):
    raw = lzma.decompress(data); n = len(raw) // 24; sc = scale(code); base = dt.datetime(y, m, 1); rows = []
    for i in range(n):
        t, o, c, l, h, v = struct.unpack(">5if", raw[i * 24:(i + 1) * 24])
        rows.append((base + dt.timedelta(seconds=t), o / sc, h / sc, l / sc, c / sc, v))
    return rows
def main():
    side = sys.argv[1]; pairs = [kv.split("=") for kv in sys.argv[2].split(",")]
    start = sys.argv[3] if len(sys.argv) > 3 else "2016-01"; end = sys.argv[4] if len(sys.argv) > 4 else "2026-08"
    months = pd.period_range(start, end, freq="M"); S = side.upper()
    for sym, code in pairs:
        out = f"data_dukascopy/{sym}_hour{'' if side == 'bid' else '_ask'}.csv.gz"
        if os.path.exists(out) and side == "bid" and sym in ("AUDJPY", "AUDUSD", "CADJPY", "CHFJPY", "EURAUD", "EURGBP", "EURJPY", "EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "NZDJPY", "NZDUSD", "USDCHF", "USDJPY", "XAUUSD", "GER40", "NAS100", "US500"):
            print(f"[{sym}] 既存 bid ファイルあり → スキップ", flush=True); continue
        cache = f"data_dukascopy/raw/{code}"; os.makedirs(cache, exist_ok=True); allrows = []; missing = 0
        for p in months:
            f = f"{cache}/{p.year}-{p.month:02d}_{side}.bi5"
            if not os.path.exists(f):
                url = f"https://datafeed.dukascopy.com/datafeed/{code}/{p.year}/{p.month - 1:02d}/{S}_candles_hour_1.bi5"
                st, data = fetch(url); time.sleep(GAP)
                if st == 200 and data: open(f, "wb").write(data)
                elif st == 404: open(f, "wb").write(b""); missing += 1
                else: print(f"[{sym}] {p} 取得失敗(st={st})→ 後で再試行", flush=True); continue
            data = open(f, "rb").read()
            if data: allrows += decode(data, code, p.year, p.month)
        if not allrows: print(f"[{sym}] データなし", flush=True); continue
        df = pd.DataFrame(allrows, columns=["timestamp", "open", "high", "low", "close", "volume"]).drop_duplicates("timestamp").sort_values("timestamp")
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        with gzip.open(out, "wt") as g: df.to_csv(g, index=False)
        print(f"[{sym}] {side} rows={len(df)} {df.timestamp.iloc[0]}〜{df.timestamp.iloc[-1]} 404={missing} → {out}", flush=True)
        try:
            subprocess.run(["git", "add", out], check=True)
            subprocess.run(["git", "commit", "-q", "-m", f"data: Dukascopy H1 {side} {sym}({code}) {start}〜{end}\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01P8mtG8UXER1rod1zfEpDhP"], check=True)
            subprocess.run(["git", "push", "-q", "-u", "origin", "claude/prop-trading-new-methods-a8y3l1"], check=True)
        except Exception as e: print(f"[{sym}] git 失敗: {e}", flush=True)
if __name__ == "__main__": main()
