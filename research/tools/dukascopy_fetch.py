# -*- coding: utf-8 -*-
"""Dukascopy datafeed から H1 ローソク(bid / ask)を月単位で取得し data_dukascopy/<SYM>_hour[_ask].csv.gz に変換する(docs/254)。
・レート制限: 1 リクエスト 9 秒間隔(4 秒で 503)。429/503/接続断は待って再試行。
・再開可能: raw キャッシュ data_dukascopy/raw/<code>/<yyyy>-<mm>_<side>.bi5(git 管理外)。
・銘柄ごとに完了したら csv.gz をコミット・push(コンテナ消失に備える)。
使い方: python3 research/tools/dukascopy_fetch.py <side bid|ask> <SYM=CODE,...> [start YYYY-MM] [end YYYY-MM] [budget_min]
・時間予算(budget_min)を超えたら現在の銘柄を部分保存(csv.gz + manifest.json)してコミット・push し終了。次回は csv.gz にある月を飛ばして再開(コンテナ再起動に耐える)。
・manifest.json: {"SYM|side": {"done": [...], "missing404": [...], "complete": bool}}
"""
import os, sys, time, lzma, struct, gzip, io, subprocess, urllib.request, urllib.error, datetime as dt
import pandas as pd, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); REPO = os.path.dirname(ROOT); os.chdir(ROOT)   # ROOT = research/
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
            wait = 40 * (k + 1); print(f"  http {e.code} → {wait}s 待機", flush=True); time.sleep(wait)
        except Exception as e:
            wait = 40 * (k + 1); print(f"  {str(e)[:40]} → {wait}s 待機", flush=True); time.sleep(wait)
    return 0, b""
def decode(data, code, y, m):
    raw = lzma.decompress(data); n = len(raw) // 24; sc = scale(code); base = dt.datetime(y, m, 1); rows = []
    for i in range(n):
        t, o, c, l, h, v = struct.unpack(">5if", raw[i * 24:(i + 1) * 24])
        rows.append((base + dt.timedelta(seconds=t), o / sc, h / sc, l / sc, c / sc, v))
    return rows
MANIFEST = "data_dukascopy/manifest.json"
def load_manifest(): return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
def save_manifest(m): json.dump(m, open(MANIFEST, "w"), ensure_ascii=False, indent=1, sort_keys=True)
def git_push(paths, msg):
    try:
        subprocess.run(["git", "-C", REPO, "add", "-f"] + [os.path.join("research", p) for p in paths], check=True)   # research/.gitignore の data*/ に該当するため -f
        subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01P8mtG8UXER1rod1zfEpDhP"], check=True)
        subprocess.run(["git", "-C", REPO, "push", "-q", "-u", "origin", "claude/prop-trading-new-methods-a8y3l1"], check=True); return True
    except Exception as e: print(f"git 失敗: {e}", flush=True); return False
def main():
    side = sys.argv[1]; pairs = [kv.split("=") for kv in sys.argv[2].split(",")]
    start = sys.argv[3] if len(sys.argv) > 3 else "2016-01"; end = sys.argv[4] if len(sys.argv) > 4 else "2026-08"
    budget = float(sys.argv[5]) * 60 if len(sys.argv) > 5 else 1e12; t_start = time.time()
    months = pd.period_range(start, end, freq="M"); S = side.upper(); man = load_manifest()
    for sym, code in pairs:
        key = f"{sym}|{side}"; out = f"data_dukascopy/{sym}_hour{'' if side == 'bid' else '_ask'}.csv.gz"
        if man.get(key, {}).get("complete"): print(f"[{sym}] {side} 完了済み → スキップ", flush=True); continue
        if os.path.exists(out) and side == "bid" and sym in ("AUDJPY", "AUDUSD", "CADJPY", "CHFJPY", "EURAUD", "EURGBP", "EURJPY", "EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "NZDJPY", "NZDUSD", "USDCHF", "USDJPY", "XAUUSD", "GER40", "NAS100", "US500"):
            print(f"[{sym}] 既存 bid ファイルあり(ユーザー提供)→ スキップ", flush=True); continue
        # 再開: 既存 csv.gz にある月は取得済みとして扱う
        old = None; have = set()
        if os.path.exists(out):
            old = pd.read_csv(out); have = set(pd.to_datetime(old["timestamp"]).dt.to_period("M").astype(str))
        miss404 = set(man.get(key, {}).get("missing404", []))
        cache = f"data_dukascopy/raw/{code}"; os.makedirs(cache, exist_ok=True); newrows = []; stopped = False
        for p in months:
            ps = str(p)
            if ps in have or ps in miss404: continue
            if time.time() - t_start > budget: stopped = True; break
            f = f"{cache}/{p.year}-{p.month:02d}_{side}.bi5"
            if not os.path.exists(f):
                url = f"https://datafeed.dukascopy.com/datafeed/{code}/{p.year}/{p.month - 1:02d}/{S}_candles_hour_1.bi5"
                st, data = fetch(url); time.sleep(GAP)
                if st == 200 and data: open(f, "wb").write(data)
                elif st == 404: miss404.add(ps); continue
                else: print(f"[{sym}] {p} 取得失敗(st={st})→ 次回再試行", flush=True); continue
            data = open(f, "rb").read()
            if data: newrows += decode(data, code, p.year, p.month)
        if newrows or old is not None:
            df = pd.DataFrame(newrows, columns=["timestamp", "open", "high", "low", "close", "volume"])
            if old is not None: df = pd.concat([old.assign(timestamp=pd.to_datetime(old["timestamp"])), df], ignore_index=True)
            df = df.drop_duplicates("timestamp").sort_values("timestamp"); df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            with gzip.open(out, "wt") as g: df.to_csv(g, index=False)
            done = sorted(set(pd.to_datetime(df["timestamp"]).dt.to_period("M").astype(str)))
            complete = (not stopped) and all((str(p) in done) or (str(p) in miss404) for p in months)
            man[key] = dict(done_months=len(done), missing404=sorted(miss404), complete=complete, first=df.timestamp.iloc[0], last=df.timestamp.iloc[-1], rows=len(df)); save_manifest(man)
            print(f"[{sym}] {side} rows={len(df)} months={len(done)} 404={len(miss404)} complete={complete}{' (時間予算で中断)' if stopped else ''} → {out}", flush=True)
            git_push([out, MANIFEST], f"data: Dukascopy H1 {side} {sym}({code}) {'完了' if complete else '部分'} {len(done)}ヶ月")
        else: print(f"[{sym}] データなし", flush=True)
        if stopped: print(f"[予算] {budget/60:.0f} 分に到達 → 終了", flush=True); return
if __name__ == "__main__": main()
