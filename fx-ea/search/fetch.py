#!/usr/bin/env python3
"""Yahoo Finance 日足フェッチ(キャッシュ付き)。"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64)"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def fetch_daily(ysym, rng="15y"):
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]", "_", ysym) + ".json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 86400:
        return json.load(open(fn))
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ysym)}?range={rng}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode())
    res = d["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(res["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or o <= 0:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append([day, o, h, l, c])
    json.dump(rows, open(fn, "w"))
    return rows


if __name__ == "__main__":
    r = fetch_daily("^GSPC")
    print("rows", len(r), r[0], r[-1])
