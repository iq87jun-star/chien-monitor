#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theoption 転売実測プローブ v0.9(お試し環境専用)。
目的: theoption_validation/README 追補21・21補足の「転売価格 vs 公正値(含み損の深さ別)」の実測。
モード:
  --live-demo : 月曜 07:00:10 JST に EURJPY / AUDJPY / NZDJPY の FE|23H|HIGHLOW|HIGH(翌 06:00 JST 判定)を ¥1,000 ずつ成行で購入
                (/trading/buy)→ 30 分ごとに trades(can_sell / sell = 転売情報)と contract_data(判定価格)を 15 秒だけ記録
                → 翌 03:00 JST に含み損の取引が有れば 1 本だけ実際に転売(/trading/sell)→ 翌 06:10 JST に /history/trades で結果を要約。
  (指定なし)  : 記録のみ。実行中の取引(ユーザーが手で置いたもの)の転売情報を翌 06:10 まで記録し、発注も転売もしない。
  --once      : 1 回だけ収集して終了(動作確認)。
安全:
  * API キーが JWT で発行者(iss)が TheOptionDemo でなければ発注・転売しない(記録もせず終了)。
  * 接続先はお試しホスト(apidemo / gatewaydemo)に固定。本番ホストはこのファイルに存在しない。
  * 発注は 1 回の実行で最大 3 本・各 ¥1,000。_diag/tenbai_state.json で同じ日の二重発注を防ぐ。残高 < ¥3,000 なら発注しない。
  * 07:10 JST を過ぎて起動した場合は今週の発注を見送る(記録のみ)。
"""
import argparse, asyncio, base64, datetime as dt, glob, json, os, sys, time, urllib.request, urllib.error
VERSION = "0.9"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc; JST = dt.timezone(dt.timedelta(hours=9))
BASE = "https://apidemo.theoption.com/v1"; WSS = "wss://gatewaydemo.theoption.com/v1/ws"   # お試し固定
PAIRS = ("EURJPY", "AUDJPY", "NZDJPY")   # 月7時→翌6時 HIGH の 3 脚(追補18 確定メニュー)
AMOUNT = 1000; MAX_BUYS = 3
BUY_AT = "07:00:10"; BUY_DEADLINE = "07:10:00"; SELL_AT = "03:00"; END_AT = "06:10"
POLL_MINUTES = 30; COLLECT_SECS = 15
SELL_ORDER = ("NZDJPY", "AUDJPY", "EURJPY")   # 転売する候補の優先順(エッジが小さい順)

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

def err_codes(resp): return [e.get("errorCode") for e in (resp or {}).get("errors", []) if isinstance(e, dict)]

def buy_body(name, expiration_time, amount=AMOUNT):
    """クイックスタート ステップ5 の成行注文。FE は order_properties.expiration_time 必須(無いと 103)。"""
    return {"contract": name, "amount": amount, "order_type": "market", "order_properties": {"expiration_time": expiration_time}}

def contract_json(values):
    c = (values or {}).get("contract")
    if isinstance(c, dict): return c
    try: return json.loads(c) if c else None
    except (TypeError, ValueError): return None

def want_name(pair): return f"{pair}|FE|23H|HIGHLOW|HIGH"

def pick_contracts(frames, now_utc):
    """contracts フレーム列から 3 脚の契約(名前・expiration_time)を選ぶ。判定が now+20h〜+25h のもの(翌 06:00 JST)。"""
    out = {}
    for fr in frames:
        if fr.get("type") != "update": continue
        c = contract_json(fr.get("values")) or {}
        name = c.get("name") or str(fr.get("key", "")).split("|20")[0]
        if c.get("status", "Open") not in ("Open", "Opened"): continue
        for p in PAIRS:
            if name == want_name(p):
                exp = c.get("expiration_time")
                try: t = dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                except Exception: continue
                if dt.timedelta(hours=20) <= t - now_utc <= dt.timedelta(hours=25): out[p] = (name, exp)
    return out

def contracts_from_probe_jsonl(out_dir, now_utc):
    """同じ out に記録プローブが書いている当日の probe_demo_*.jsonl から契約を拾う(WS を増やさない)。"""
    today = dt.datetime.now(JST).strftime("%Y%m%d"); frames = []
    for path in sorted(glob.glob(os.path.join(out_dir, f"probe_demo_{today}_*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try: rec = json.loads(line)
                    except ValueError: continue
                    if rec.get("kind") == "ws": frames.append(rec.get("frame") or {})
        except OSError: continue
    return pick_contracts(frames, now_utc)

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

async def ws_collect(key, contract_names, secs, want_contracts=False):
    """WS を開き、trades(+contract_data、必要なら contracts)を secs 秒だけ集めて閉じる。"""
    import websockets
    hdr = {"Authorization": "Bearer " + key}; frames = []
    try: conn = websockets.connect(WSS, additional_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    except TypeError: conn = websockets.connect(WSS, extra_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    async with conn as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 30)); frames.append(first)
        if first.get("type") != "ready": return frames
        rid = 1
        await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "trades"}))
        if want_contracts:
            rid += 1; await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contracts"}))
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
            # 実行中の取引が新しく見えたら、その契約の判定価格も購読する(手で置かれた取引は契約名が事前に分からないため)
            if fr.get("type") == "update" and fr.get("stream") != "contract_data" and "asset" not in (fr.get("values") or {}):
                name = trade_contract(fr)
                if name and name not in subscribed and len(subscribed) < 20:
                    subscribed.add(name); rid += 1
                    await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contract_data", "contract": name}))
    return frames

def snapshot(frames, known=None):
    """フレーム列から {取引ID: {contract, can_sell, sell, rate, strike, depth_pip, row}} を作る。known は購入応答から分かっている strike。"""
    trades = {}; rates = {}; known = known or {}
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
        tid = str(fr.get("key", "")); strike = deep_find(v, "strike")
        if strike is None and tid in known: strike = known[tid].get("strike")
        trades[tid] = {"contract": name, "can_sell": deep_find(v, "can_sell"), "sell": v.get("sell"), "strike": strike, "row": fr}
    for tid, t in trades.items():
        rate = rates.get(t["contract"]); t["rate"] = rate
        try: t["depth_pip"] = (rate - float(t["strike"])) / (0.01 if t["contract"].split("|")[0].endswith("JPY") else 0.0001)
        except (TypeError, ValueError): t["depth_pip"] = None
    return trades

def keep_awake():
    """実行中は Windows をスリープさせない(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)。"""
    if os.name != "nt": return
    try:
        import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    except Exception: pass

class Log:
    def __init__(self, path): self.path = path; os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    def write(self, kind, obj):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"recv_utc": dt.datetime.now(UTC).isoformat(), "kind": kind, "frame": obj}, ensure_ascii=False) + "\n")
    def say(self, *a): print(dt.datetime.now(JST).strftime("%m/%d %H:%M:%S"), *a, flush=True)

def jst_at(hhmmss, base=None, days=0):
    base = base or dt.datetime.now(JST); parts = list(map(int, hhmmss.split(":"))) + [0, 0]
    return base.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0) + dt.timedelta(days=days)

def sleep_until(t):
    while True:
        s = (t - dt.datetime.now(JST)).total_seconds()
        if s <= 0: return
        time.sleep(min(s, 60))

def place_orders(key, contracts, log, bal):
    """3 脚を ¥1,000 ずつ成行で購入。戻り値: 購入できた取引のリスト。"""
    trades = []
    if bal is None or float(bal) < AMOUNT * len(PAIRS):
        log.say("残高不足(", bal, ")→ 発注しない"); log.write("guard", {"balance": bal}); return trades
    for p in PAIRS:
        if len(trades) >= MAX_BUYS: break
        if p not in contracts: log.say(p, "の契約が無い → 見送り"); continue
        name, exp = contracts[p]; resp = None
        for attempt in range(2):
            st, resp = rest("/trading/buy", key, buy_body(name, exp))
            log.write("buy", {"pair": p, "http": st, "req": buy_body(name, exp), "body": resp})
            if resp.get("status") == "success": break
            codes = err_codes(resp); log.say(p, "buy 拒否", codes, str(resp)[:200])
            if not (set(codes) & {224, 213, 214, 216, 999}): break   # 再試行して意味のある拒否だけ 1 回だけやり直す
            time.sleep(2)
        if resp and resp.get("status") == "success":
            d = resp.get("data") or {}; op = d.get("order_properties") or {}
            trades.append({"pair": p, "contract": name, "trade": str(d.get("trade")), "option": d.get("option"), "strike": op.get("strike"),
                           "strike_id": op.get("strike_id"), "trading_time": d.get("trading_time"), "close_time": d.get("close_time")})
            log.say(p, "購入", d.get("trade"), "strike", op.get("strike"))
        time.sleep(1.2)   # 購入は 1 秒に 1 回まで
    return trades

def try_sell_one(key, snap, trades, log):
    """翌 03:00: 含み損で can_sell が偽でない取引を優先順に 1 本だけ転売。戻り値: 結果 dict。"""
    for p in SELL_ORDER:
        t = next((x for x in trades if x["pair"] == p), None)
        v = snap.get(t["trade"]) if t else None
        if not t or not v or v["depth_pip"] is None or v["depth_pip"] >= 0 or v["can_sell"] in (False, "false", "False"): continue
        st, resp = rest("/trading/sell", key, {"tradeActionID": int(t["trade"])})
        log.write("sell", {"pair": p, "http": st, "body": resp, "at_depth_pip": v["depth_pip"], "quote": v["sell"]})
        log.say(p, "転売", st, str(resp)[:200])
        return {"pair": p, "trade": t["trade"], "depth_pip": v["depth_pip"], "quote": v["sell"], "resp": resp}
    return {"pair": None, "note": "含み損で転売可能な取引が無く転売せず"}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-demo", action="store_true", help="お試し環境で実際に ¥1,000 × 3 本を置き、翌 03:00 に 1 本転売する")
    ap.add_argument("--once", action="store_true", help="1 回だけ収集して終了(動作確認)")
    ap.add_argument("--out", default=os.environ.get("THEOPTION_OUT") or os.path.join(HERE, "out")); a = ap.parse_args(argv)
    key = os.environ.get("THEOPTION_API_KEY", "").strip()
    now = dt.datetime.now(JST); log = Log(os.path.join(a.out, f"tenbai_demo_{now:%Y%m%d_%H%M}.jsonl"))
    if not key: log.say("環境変数 THEOPTION_API_KEY が無い"); return 2
    if not is_demo_key(key): log.say("キーがお試し用(iss=TheOptionDemo)ではない → 終了"); log.write("guard", {"iss": jwt_iss(key)}); return 3
    keep_awake()
    st, h = rest("/trading/health", key); log.write("health", {"http": st, "body": h}); log.say("health:", st)
    if st != 200 or h.get("status") == "fail": log.say("health 失敗。終了"); return 1
    st, b = rest("/wallet/balance", key); log.write("balance", {"http": st, "body": b}); bal = deep_find(b, "balance"); log.say("balance:", bal)
    state_path = os.path.join(a.out, "_diag", "tenbai_state.json"); os.makedirs(os.path.dirname(state_path), exist_ok=True)
    try: state = json.load(open(state_path, encoding="utf-8"))
    except Exception: state = {}
    day = now.strftime("%Y-%m-%d"); trades = state.get("trades", []) if state.get("day") == day else []; sold = state.get("sold") if state.get("day") == day else None
    # 1) 発注(--live-demo のみ。07:10 までに起動していて、当日まだ発注していない場合)
    if a.live_demo and not trades and not a.once:
        if now <= jst_at(BUY_DEADLINE):
            now_utc = dt.datetime.now(UTC); contracts = contracts_from_probe_jsonl(a.out, now_utc)
            if len(contracts) < len(PAIRS):
                log.say("記録プローブの JSONL に契約が足りない → contracts を 30 秒購読")
                try:
                    frs = asyncio.run(ws_collect(key, [], 30, want_contracts=True)); log.write("contracts_scan", {"n": len(frs)})
                    contracts.update({p: v for p, v in pick_contracts(frs, now_utc).items() if p not in contracts})
                except Exception as e: log.write("error", repr(e)); log.say("contracts 購読に失敗:", repr(e))
            log.write("contracts", contracts); log.say("契約:", contracts)
            sleep_until(jst_at(BUY_AT))
            trades = place_orders(key, contracts, log, bal)
            state = {"day": day, "trades": trades}; json.dump(state, open(state_path, "w", encoding="utf-8"), ensure_ascii=False)
        else:
            log.say("07:10 JST を過ぎている → 今週は発注しない(記録のみ)")
    known = {t["trade"]: t for t in trades}
    # 2) 30 分ごとの収集 → 3) 翌 03:00 の転売(--live-demo・1 本) → 4) 翌 06:10 の履歴
    end = jst_at(END_AT); end = end if end > now else end + dt.timedelta(days=1)
    sell_at = jst_at(SELL_AT); sell_at = sell_at if sell_at > now else sell_at + dt.timedelta(days=1)
    names = [t["contract"] for t in trades]; polls = []
    nxt = now.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    while True:
        try: frs = asyncio.run(ws_collect(key, names, COLLECT_SECS))
        except Exception as e: frs = []; log.write("error", repr(e)); log.say("収集に失敗:", repr(e))
        snap = snapshot(frs, known); names = sorted({t["contract"] for t in snap.values()} | set(names))[:20]
        polls.append({"jst": dt.datetime.now(JST).strftime("%m/%d %H:%M"), "trades": snap}); log.write("poll", polls[-1])
        log.say("poll", {tid: (t["contract"].split("|")[0], None if t["depth_pip"] is None else round(t["depth_pip"], 1), t["can_sell"]) for tid, t in snap.items()} or "実行中の取引なし")
        if a.once: break
        if a.live_demo and trades and not sold and dt.datetime.now(JST) >= sell_at:
            sold = try_sell_one(key, snap, trades, log); state["sold"] = sold
            json.dump(state, open(state_path, "w", encoding="utf-8"), ensure_ascii=False)
        nxt += dt.timedelta(minutes=POLL_MINUTES - ((nxt.minute - 1) % POLL_MINUTES) - 1) if len(polls) == 1 else dt.timedelta(minutes=POLL_MINUTES)
        if sell_at > dt.datetime.now(JST) and nxt > sell_at: nxt = sell_at   # 転売時刻ぴったりにも 1 回収集する
        if nxt >= end: break
        sleep_until(nxt)
    t0 = dt.datetime.now(UTC) - dt.timedelta(hours=26)
    st, hist = rest("/history/trades", key, {"reportFromTime": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "reportToTime": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    log.write("history", {"http": st, "body": hist})
    write_summary(log, trades, polls, sold, hist, a.out); return 0

def write_summary(log, trades, polls, sold, hist, out_dir):
    L = [f"転売実測 v{VERSION}  {dt.datetime.now(JST):%Y-%m-%d %H:%M} JST", ""]
    L.append("(1) 購入(このプローブが置いた取引): " + json.dumps(trades, ensure_ascii=False))
    L.append(""); L.append("(2) 30 分ごとの転売情報(depth = 判定価格 − ストライク, pip)")
    for s in polls:
        if not s["trades"]: L.append(f" {s['jst']}  実行中の取引なし"); continue
        L.append(f" {s['jst']}  " + "  ".join(f"[{tid}] {t['contract'].split('|')[0]}: depth={None if t['depth_pip'] is None else round(t['depth_pip'],1)} can_sell={t['can_sell']} sell={json.dumps(t['sell'], ensure_ascii=False)[:160]}" for tid, t in s["trades"].items()))
    L.append(""); L.append("(3) 転売の実行: " + json.dumps(sold, ensure_ascii=False))
    L.append(""); L.append("(4) 取引履歴(/history/trades): " + json.dumps(hist, ensure_ascii=False)[:4000])
    txt = "\n".join(L) + "\n"; print(txt)
    with open(log.path[:-6] + ".summary.txt", "w", encoding="utf-8") as f: f.write(txt)
    d = os.path.join(out_dir, "_diag"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "tenbai_last_run.txt"), "w", encoding="utf-8") as f:
        f.write(f"version={VERSION}\nfinished_jst={dt.datetime.now(JST):%Y-%m-%d %H:%M:%S}\nfile={os.path.basename(log.path)}\ntrades={len(trades)}\npolls={len(polls)}\nsold={json.dumps(sold, ensure_ascii=False)[:200]}\n")

if __name__ == "__main__": sys.exit(main())
