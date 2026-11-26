#!/usr/bin/env python3
"""FXCM 公開 1 分足(週ごとの csv.gz)を取得する。使い方: python3 fetch_fxcm.py <出力先> <開始年> <終了年> PAIR [PAIR...]
例: python3 fetch_fxcm.py /tmp/cache/fxcm 2016 2026 EURUSD GBPUSD
- 取得済みのファイルは飛ばす。User-Agent が無いと 403 になる。週 N のファイルはその週の終了後に公開される。2026 年の 18〜31 週は配信元に無い。
- 提供されない通貨: NZDJPY・CHFJPY・CADJPY(CHFJPY・CADJPY は USDJPY ÷ USDCHF / USDCAD で合成する)。"""
import sys, os, urllib.request, concurrent.futures as cf
out, y0, y1, pairs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
os.makedirs(out, exist_ok=True)
jobs = [(p, y, w) for p in pairs for y in range(y0, y1 + 1) for w in range(1, 54)]
def get(j):
    p, y, w = j; f = f"{out}/{p}_{y}_{w}.csv.gz"
    if os.path.exists(f) and os.path.getsize(f) > 0: return True
    try:
        req = urllib.request.Request(f"https://candledata.fxcorporate.com/m1/{p}/{y}/{w}.csv.gz", headers={"User-Agent": "Mozilla/5.0"})
        b = urllib.request.urlopen(req, timeout=90).read(); open(f, "wb").write(b); return True
    except Exception: return False
with cf.ThreadPoolExecutor(12) as ex: r = list(ex.map(get, jobs))
print(sum(r), "/", len(jobs))
