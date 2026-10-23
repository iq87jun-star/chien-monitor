#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theoption 転売情報の記録プローブ v0.9(お試し環境専用・記録のみ・発注も転売もしない)。
目的: theoption_validation/README 追補21・21補足の「転売価格 vs 公正値(含み損の深さ別)」の実測。
前提: お試し(API)口座に実行中の取引があること。取引そのものは本スクリプトでは行わない(ユーザーが置く)。
やること(月曜 07:05 JST にタスク起動 → 翌 06:10 JST まで常駐):
  1. ガード: API キーが JWT で発行者(iss)が TheOptionDemo でなければ終了。接続先は apidemo / gatewaydemo 固定(本番ホストは持たない)。
  2. 30 分ごと: WS を開いて trades(実行中の取引・can_sell / sell = 転売情報)と、その取引の契約の contract_data(判定価格)を
     15 秒だけ集めて JSONL に記録し、閉じる。
  3. 翌 06:10 JST: /history/trades で結果(income 等)を取り、要約 tenbai_demo_<日時>.summary.txt を out に書く。
使い方: python to_tenbai.py            # タスクから(翌 06:10 まで常駐)
        python to_tenbai.py --once     # 1 回だけ収集して終了(動作確認)
"""
import argparse, asyncio, base64, datetime as dt, json, os, sys, time, urllib.request, urllib.error
VERSION = "0.9"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc; JST = dt.timezone(dt.timedelta(hours=9))
BASE = "https://apidemo.theoption.com/v1"; WSS = "wss://gatewaydemo.theoption.com/v1/ws"   # お試し固定
END_AT = "06:10"; POLL_MINUTES = 30; COLLECT_SECS = 15

def jwt_iss(key):
    """API キー(JWT)の発行者。壊れていれば None。"""
    try:
        p = key.split(".")[1]; p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p).decode("utf-8")).get("iss")
    except Exception: return None

def is_demo_key(key): return jwt_iss(key) == "TheOptionDemo"

def rest(path, key, body=None, timeout=15):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore")
        try: return e.code, json.loads(b)
        except ValueError: return e.code, {"raw": b[:500]}
    except Exception as e: return None, {"error": repr(e)}

def deep_find(obj, key):
    """入れ子の dict / JSON 文字列から key を探す(trades フレームの can_sell 等。欄の位置が公開資料で未確定なため)。"""
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = deep_find(v, key)
            if r is not None: return r
    elif isinstance(obj, list):
        for v in obj:
            r = deep_find(v, key)
            if r is not None: return r
    elif isinstance(obj, str) and obj[:1] in "{[":
        try: return deep_find(json.loads(obj), key)
        except ValueError: return None
    return None

def trade_contract(fr):
    """trades フレームから契約名(資産|FE|23H|HIGHLOW|HIGH …)を取り出す。無ければ None。"""
    v = fr.get("values") or {}
    for k in ("contract", "contract_name", "name"):
        r = deep_find(v, k)
        if isinstance(r, str) and "|" in r: return r
    return None

async def ws_collect(key, contract_names, secs):
    """WS を開き、trades(+contract_data)を secs 秒だけ集めて閉じる。"""
    import websockets
    hdr = {"Authorization": "Bearer " + key}; frames = []
    try: conn = websockets.connect(WSS, additional_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    except TypeError: conn = websockets.connect(WSS, extra_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    async with conn as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 30)); frames.append(first)
        if first.get("type") != "ready": return frames
        rid = 1
        await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "trades"}))
        subscribed = set(contract_names)
        for name in contract_names:
            rid += 1; await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contract_data", "contract": name}))
        t_end = time.time() + secs
        while time.time() < t_end:
            try: raw = await asyncio.wait_for(ws.recv(), max(1, t_end - time.time()))
            except asyncio.TimeoutError: break
            try: fr = json.loads(raw)
            except ValueError: frames.append({"raw": raw[:2000]}); continue
            frames.append(fr)
            # 実行中の取引が新しく見えたら、その契約の判定価格も購読する(初回は契約名が分からないため)
            if fr.get("type") == "update" and fr.get("stream") != "contract_data":
                name = trade_contract(fr)
                if name and name not in subscribed and len(subscribed) < 20:
                    subscribed.add(name); rid += 1
                    await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contract_data", "contract": name}))
    return frames

def snapshot(frames):
    """フレーム列から {取引ID: {contract, can_sell, sell, rate, strike, depth_pip, row}} を作る。"""
    trades = {}; rates = {}
    for fr in frames:
        if fr.get("type") != "update": continue
        v = fr.get("values") or {}
        if "asset" in v or fr.get("stream") == "contract_data":
            r = deep_find(v, "rate"); k = str(fr.get("key", ""))
            try: rates[k.split("|20")[0]] = float(r)
            except (TypeError, ValueError): pass
            continue
        name = trade_contract(fr)
        if not name: continue
        strike = deep_find(v, "strike")
        trades[str(fr.get("key", ""))] = {"contract": name, "can_sell": deep_find(v, "can_sell"), "sell": v.get("sell"), "strike": strike, "row": fr}
    for tid, t in trades.items():
        rate = rates.get(t["contract"]); t["rate"] = rate
        try: t["depth_pip"] = (rate - float(t["strike"])) / (0.01 if t["contract"].split("|")[0].endswith("JPY") else 0.0001)
        except (TypeError, ValueError): t["depth_pip"] = None
    return trades

class Log:
    def __init__(self, path): self.path = path; os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    def write(self, kind, obj):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"recv_utc": dt.datetime.now(UTC).isoformat(), "kind": kind, "frame": obj}, ensure_ascii=False) + "\n")
    def say(self, *a): print(dt.datetime.now(JST).strftime("%m/%d %H:%M:%S"), *a, flush=True)

def sleep_until(t):
    while True:
        s = (t - dt.datetime.now(JST)).total_seconds()
        if s <= 0: return
        time.sleep(min(s, 60))

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--once", action="store_true", help="1 回だけ収集して終了(動作確認)")
    ap.add_argument("--out", default=os.environ.get("THEOPTION_OUT") or os.path.join(HERE, "out")); a = ap.parse_args(argv)
    key = os.environ.get("THEOPTION_API_KEY", "").strip()
    now = dt.datetime.now(JST); log = Log(os.path.join(a.out, f"tenbai_demo_{now:%Y%m%d_%H%M}.jsonl"))
    if not key: log.say("環境変数 THEOPTION_API_KEY が無い"); return 2
    if not is_demo_key(key): log.say("キーがお試し用(iss=TheOptionDemo)ではない → 終了"); log.write("guard", {"iss": jwt_iss(key)}); return 3
    st, h = rest("/trading/health", key); log.write("health", {"http": st, "body": h}); log.say("health:", st)
    if st != 200 or h.get("status") == "fail": log.say("health 失敗。終了"); return 1
    st, b = rest("/wallet/balance", key); log.write("balance", {"http": st, "body": b}); log.say("balance:", deep_find(b, "balance"))
    end = now.replace(hour=int(END_AT[:2]), minute=int(END_AT[3:]), second=0, microsecond=0)
    if end <= now: end += dt.timedelta(days=1)
    names = []; polls = []
    nxt = now.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    while True:
        try: frs = asyncio.run(ws_collect(key, names, COLLECT_SECS))
        except Exception as e: frs = []; log.write("error", repr(e)); log.say("収集に失敗:", repr(e))
        snap = snapshot(frs); names = sorted({t["contract"] for t in snap.values()} | set(names))[:20]
        polls.append({"jst": dt.datetime.now(JST).strftime("%m/%d %H:%M"), "trades": snap}); log.write("poll", polls[-1])
        log.say("poll", {tid: (t["contract"].split("|")[0], None if t["depth_pip"] is None else round(t["depth_pip"], 1), t["can_sell"]) for tid, t in snap.items()} or "実行中の取引なし")
        if a.once: break
        nxt += dt.timedelta(minutes=POLL_MINUTES - ((nxt.minute - 1) % POLL_MINUTES) - 1) if len(polls) == 1 else dt.timedelta(minutes=POLL_MINUTES)
        if nxt >= end: break
        sleep_until(nxt)
    t0 = dt.datetime.now(UTC) - dt.timedelta(hours=26)
    st, hist = rest("/history/trades", key, {"reportFromTime": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "reportToTime": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    log.write("history", {"http": st, "body": hist})
    write_summary(log, polls, hist, a.out); return 0

def write_summary(log, polls, hist, out_dir):
    L = [f"転売情報の記録 v{VERSION}  {dt.datetime.now(JST):%Y-%m-%d %H:%M} JST", ""]
    L.append("(1) 30 分ごとの転売情報(depth = 判定価格 − ストライク, pip)")
    for s in polls:
        if not s["trades"]: L.append(f" {s['jst']}  実行中の取引なし"); continue
        L.append(f" {s['jst']}  " + "  ".join(f"[{tid}] {t['contract'].split('|')[0]}: depth={None if t['depth_pip'] is None else round(t['depth_pip'],1)} can_sell={t['can_sell']} sell={json.dumps(t['sell'], ensure_ascii=False)[:160]}" for tid, t in s["trades"].items()))
    L.append(""); L.append("(2) 取引履歴(/history/trades): " + json.dumps(hist, ensure_ascii=False)[:4000])
    txt = "\n".join(L) + "\n"; print(txt)
    with open(log.path[:-6] + ".summary.txt", "w", encoding="utf-8") as f: f.write(txt)
    d = os.path.join(out_dir, "_diag"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "tenbai_last_run.txt"), "w", encoding="utf-8") as f:
        f.write(f"version={VERSION}\nfinished_jst={dt.datetime.now(JST):%Y-%m-%d %H:%M:%S}\nfile={os.path.basename(log.path)}\npolls={len(polls)}\n")

if __name__ == "__main__": sys.exit(main())
