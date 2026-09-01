#!/usr/bin/env python3
"""Yahoo Finance 日足フェッチ(キャッシュ付き)。"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64)"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def fetch_daily(ysym, rng="15y"):
    """[日付, 始, 高, 安, 終, 出来高] の配列を返す。

    出来高は指数・商品でのみ有効。FXは Yahoo が常に 0 を返すので使えない。
    5要素だった旧形式のキャッシュは自動で取り直す。
    """
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]", "_", ysym) + ".json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 86400:
        cached = json.load(open(fn))
        if cached and len(cached[0]) >= 6:
            return cached
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ysym)}?range={rng}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
    except Exception as ex:
        # 429等で取れないときは、期限切れでも手元のキャッシュで続行する。
        # 15年の統計に1日の鮮度差は効かない。朝の自動実行を止めないほうが大事。
        if os.path.exists(fn):
            cached = json.load(open(fn))
            if cached and len(cached[0]) >= 6:
                print(f"fetch: {ysym} の取得に失敗({type(ex).__name__})。"
                      f"キャッシュ({cached[-1][0]}まで)で続行")
                return cached
        raise
    res = d["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = []
    vol = q.get("volume") or [None] * len(res["timestamp"])
    for i, ts in enumerate(res["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or o <= 0:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append([day, o, h, l, c, vol[i] or 0])
    json.dump(rows, open(fn, "w"))
    return rows


if __name__ == "__main__":
    r = fetch_daily("^GSPC")
    print("rows", len(r), r[0], r[-1])
