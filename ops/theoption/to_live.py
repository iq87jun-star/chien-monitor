#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theoption 本番メニューの自動発注 v1.3(既定はお試し口座。実口座は to_config.json の二重オプトインが要る)。
メニュー: theoption_validation/README.md 追補29裁定(勝率上位10セルのみ・既存4脚なし、DD予算40万円のEdge比例配分、月期待 +69,646円)。
動作(タスク chien_theoption_live_*: 月 06:58/09:58/12:58/13:58/15:58/17:58/20:58、火 00:58/23:58、水 01:58、毎日 22:58 に起動 → 直後の定刻の脚だけ実行して終了。
      日付をまたぐ定刻(火 23:58 起動 → 水 00:00 建て)は翌日の脚として扱う):
  1. ガード: 口座種別に合うキー(お試し= JWT iss が TheOptionDemo)。health → 残高 ≥ 今回のベット合計。
  2. 定刻(HH:MM:10 JST)に contracts ストリームを 20 秒集め、「銘柄 | FE | * | HIGHLOW | HIGH/LOW」で判定時刻が一致する契約を選ぶ
     (期間ラベルは問わない。無ければ「契約なし」で見送り=判定時刻が未確認の脚を安全に扱う)。
  3. 倍率規則(追補17): 1H は 1.85 未満・22H/23H は 1.90 未満なら見送り、2.0 以上ならベット 1.5 倍(上限 20 万円)。
  4. 成行で購入(/trading/buy)。1 秒に 1 回。_diag/live_state.json で同じ日・同じ脚の二重発注を防ぐ。
  5. 記録: out/live_<口座>_<日付>.jsonl、out/live_entries_<口座>.csv(date,strategy_id,pair,direction,payout_actual,stake,trade_id,strike,note)。
     --settle で /history/trades を引いて out/live_trades_<口座>.csv に結果(income 等)を追記(週次突合用)。
使い方: python to_live.py            # 定刻の脚を実行(タスクから)
        python to_live.py --settle   # 直近 3 日の取引結果を取り込む(毎日 06:40 のタスク)
        python to_live.py --plan     # 今日これから実行する脚を表示して終了(発注しない)
"""
import argparse, asyncio, base64, csv, datetime as dt, json, os, random, sys, time, urllib.request, urllib.error
VERSION = "1.3"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc; JST = dt.timezone(dt.timedelta(hours=9))
HOSTS = {"demo": ("https://apidemo.theoption.com/v1", "wss://gatewaydemo.theoption.com/v1/ws"),
         "real": ("https://api.theoption.com/v1", "wss://gateway.theoption.com/v1/ws")}
MAX_STAKE = 200000; SCAN_SECS = 20; DAILY_STAKE_CAP = 120000   # 1 日のベット合計の上限(v1.3 月曜 7 本 67,600 円、倍率 2.0 で 1.5 倍でも 101,400)
# 確定メニュー(追補18)。entry = JST の定刻、judge = 判定時刻 JST(next=翌日)、wds = 曜日(0=月)、months = 対象月(None=全月)
MENU = [
 # v1.3 (2026-10-27 追補29裁定): 勝率上位10セルのみ(既存4脚は外す)。2,753セル走査→ゲート通過122→全期間勝率順の上位10。DD予算40万円のEdge比例配分(100円丸め)。
 #   8本は月曜セッションの円クロスHIGH(建て時刻違い=分割エントリー)、2本は深夜建て(水 00:00 GBPJPY / 水 02:00 AUDJPY)。
 #   next=False の脚は同日 06:00 判定(深夜建て)。wds は「建てる日」の曜日(火 01:00 建て→wds=[1])。
 dict(id="AUDJPY_M10",  pair="AUDJPY", sel="HIGH", entry="10:00", judge="06:00", next=True,  stake=9800,  wds=[0], months=None, kind="23H"),
 dict(id="EURJPY_M13",  pair="EURJPY", sel="HIGH", entry="13:00", judge="06:00", next=True,  stake=9800,  wds=[0], months=None, kind="23H"),
 dict(id="EURJPY_M14",  pair="EURJPY", sel="HIGH", entry="14:00", judge="06:00", next=True,  stake=9600,  wds=[0], months=None, kind="23H"),
 dict(id="USDJPY_M14",  pair="USDJPY", sel="HIGH", entry="14:00", judge="06:00", next=True,  stake=9600,  wds=[0], months=None, kind="23H"),
 dict(id="EURJPY_M16",  pair="EURJPY", sel="HIGH", entry="16:00", judge="06:00", next=True,  stake=10400, wds=[0], months=None, kind="23H"),
 dict(id="USDJPY_M18",  pair="USDJPY", sel="HIGH", entry="18:00", judge="06:00", next=True,  stake=9400,  wds=[0], months=None, kind="23H"),
 dict(id="EURJPY_M21",  pair="EURJPY", sel="HIGH", entry="21:00", judge="06:00", next=True,  stake=9000,  wds=[0], months=None, kind="23H"),
 dict(id="EURJPY_T01",  pair="EURJPY", sel="HIGH", entry="01:00", judge="06:00", next=False, stake=9400,  wds=[1], months=None, kind="23H"),   # 月曜セッション末尾(火 01:00 建て→火 06:00)
 dict(id="GBPJPY_W00",  pair="GBPJPY", sel="HIGH", entry="00:00", judge="06:00", next=False, stake=9600,  wds=[2], months=None, kind="23H"),   # 火曜セッション末尾(水 00:00 建て→水 06:00)
 dict(id="AUDJPY_W02",  pair="AUDJPY", sel="HIGH", entry="02:00", judge="06:00", next=False, stake=8900,  wds=[2], months=None, kind="23H"),   # 同上(水 02:00 建て→水 06:00)
]
MIN_PAYOUT = {"1H": 1.85, "23H": 1.90}; BOOST_PAYOUT = 2.0; BOOST_MULT = 1.5

def jwt_iss(key):
    try:
        p = key.split(".")[1]; p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p).decode("utf-8")).get("iss")
    except Exception: return None

def rest(base, path, key, body=None, timeout=15):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore")
        try: return e.code, json.loads(b)
        except ValueError: return e.code, {"raw": b[:500]}
    except Exception as e: return None, {"error": repr(e)}

def err_codes(resp): return [e.get("errorCode") for e in (resp or {}).get("errors", []) if isinstance(e, dict)]

def deep_find(obj, key):
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

def contract_json(values):
    c = (values or {}).get("contract")
    if isinstance(c, dict): return c
    try: return json.loads(c) if c else None
    except (TypeError, ValueError): return None

def jst(day, hhmm):
    h, m = map(int, hhmm.split(":")); return dt.datetime(day.year, day.month, day.day, h, m, tzinfo=JST)

def judge_utc(leg, day):
    t = jst(day, leg["judge"]) + dt.timedelta(days=1 if leg["next"] else 0); return t.astimezone(UTC)

def is_due_today(leg, day):
    return day.weekday() in leg["wds"] and (leg["months"] is None or day.month in leg["months"])

def legs_for_slot(now_jst, window_min=5):
    """今から window_min 分以内に定刻が来る(または定刻から 3 分以内の)脚。日付をまたぐ定刻(23:58 起動→00:00 建て)は翌日の脚として拾う。
    返す脚には "_day"(建てる日)が付く(同じ時間帯の脚は同じ日)。"""
    out = []
    for day in (now_jst.date(), now_jst.date() + dt.timedelta(days=1)):
        for leg in MENU:
            if not is_due_today(leg, day): continue
            t = jst(day, leg["entry"]); d = (t - now_jst).total_seconds()
            if -180 <= d <= window_min * 60: out.append(dict(leg, _day=day))
    return out

def stake_for(leg, payout):
    """倍率規則: 下限未満は 0(見送り)、BOOST 以上は 1.5 倍(上限 MAX_STAKE)。"""
    try: p = float(payout)
    except (TypeError, ValueError): return 0
    if p < MIN_PAYOUT[leg["kind"]]: return 0
    s = leg["stake"] * (BOOST_MULT if p >= BOOST_PAYOUT else 1.0); return int(min(MAX_STAKE, s))

def pick_contract(frames, leg, day):
    """contracts フレーム列から、銘柄・HIGH/LOW・判定時刻(UTC)が一致する Open の HIGHLOW 契約を選ぶ。期間ラベルは問わない。"""
    want = judge_utc(leg, day); best = None
    for fr in frames:
        if fr.get("type") != "update": continue
        c = contract_json(fr.get("values")) or {}
        name = c.get("name") or str(fr.get("key", "")).split("|20")[0]; parts = name.split("|")
        if len(parts) < 5 or parts[0] != leg["pair"] or parts[1] != "FE" or parts[3] != "HIGHLOW" or parts[4] != leg["sel"]: continue
        if c.get("status", "Open") not in ("Open", "Opened"): continue
        try: t = dt.datetime.fromisoformat(str(c.get("expiration_time")).replace("Z", "+00:00"))
        except Exception: continue
        if abs((t - want).total_seconds()) <= 60:
            best = {"name": name, "expiration_time": c.get("expiration_time"), "payout": c.get("payout_multiplier"), "cutoff": c.get("cutoff_time")}
    return best

def buy_body(name, expiration_time, amount):
    return {"contract": name, "amount": int(amount), "order_type": "market", "order_properties": {"expiration_time": expiration_time}}

async def scan_contracts(wss, key, secs):
    import websockets
    hdr = {"Authorization": "Bearer " + key}; frames = []
    try: conn = websockets.connect(wss, additional_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    except TypeError: conn = websockets.connect(wss, extra_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    async with conn as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 30)); frames.append(first)
        if first.get("type") != "ready": return frames
        await ws.send(json.dumps({"type": "subscribe", "reqId": "1", "stream": "contracts"}))
        t_end = time.time() + secs
        while time.time() < t_end:
            try: raw = await asyncio.wait_for(ws.recv(), max(1, t_end - time.time()))
            except asyncio.TimeoutError: break
            try: frames.append(json.loads(raw))
            except ValueError: pass
    return frames

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

def append_csv(path, header, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(header)
        w.writerow(row)

def load_account(out_dir):
    """to_config.json の live_real が true かつ THEOPTION_API_KEY_REAL が有るときだけ実口座。それ以外はお試し。"""
    cfg = {}
    try: cfg = json.load(open(os.path.join(HERE, "to_config.json"), encoding="utf-8"))
    except Exception: pass
    if cfg.get("live_real") is True and os.environ.get("THEOPTION_API_KEY_REAL", "").strip():
        return "real", os.environ["THEOPTION_API_KEY_REAL"].strip()
    return "demo", os.environ.get("THEOPTION_API_KEY", "").strip()

def key_matches_account(account, key):
    iss = jwt_iss(key)
    return (iss == "TheOptionDemo") if account == "demo" else (iss is not None and iss != "TheOptionDemo")

def sleep_until(t):
    while True:
        s = (t - dt.datetime.now(JST)).total_seconds()
        if s <= 0: return
        time.sleep(min(s, 30))

def run_entries(account, key, out_dir, log, now_jst):
    base, wss = HOSTS[account]; legs = legs_for_slot(now_jst)
    if not legs: log.say("この時間帯に実行する脚は無い"); return 0
    day = legs[0]["_day"]   # v1.2: 建てる日(深夜の脚は起動日の翌日)。state/CSV/契約照合はすべてこの日で扱う
    state_path = os.path.join(out_dir, "_diag", "live_state.json"); os.makedirs(os.path.dirname(state_path), exist_ok=True)
    try: state = json.load(open(state_path, encoding="utf-8"))
    except Exception: state = {}
    done = state.get(str(day), {}); legs = [l for l in legs if l["id"] not in done]
    if not legs: log.say("この時間帯の脚は実行済み"); return 0
    st, h = rest(base, "/trading/health", key); log.write("health", {"http": st, "body": h})
    if st != 200 or h.get("status") == "fail": log.say("health 失敗 → 発注しない"); return 1
    st, b = rest(base, "/wallet/balance", key); bal = deep_find(b, "balance"); log.write("balance", {"http": st, "body": b}); log.say("balance:", bal)
    need = sum(l["stake"] * BOOST_MULT for l in legs)
    if bal is None or float(bal) < need: log.say(f"残高 {bal} < 必要 {need:.0f} → 発注しない"); log.write("guard", {"balance": bal, "need": need}); return 1
    today_total = sum(v.get("stake", 0) for v in done.values())
    entry_t = jst(day, legs[0]["entry"]) + dt.timedelta(seconds=10); sleep_until(entry_t)
    try: frames = asyncio.run(scan_contracts(wss, key, SCAN_SECS))
    except Exception as e: frames = []; log.write("error", repr(e)); log.say("contracts 購読に失敗:", repr(e))
    log.write("scan", {"n": len(frames)})
    csv_path = os.path.join(out_dir, f"live_entries_{account}.csv")
    hdr = ["date", "strategy_id", "pair", "direction", "payout_actual", "stake", "trade_id", "strike", "contract", "note"]
    for leg in legs:
        c = pick_contract(frames, leg, day); rec = {"stake": 0, "note": ""}
        if not c:
            rec["note"] = "契約なし(判定時刻が一致する HIGHLOW が無い)"; log.say(leg["id"], rec["note"]); log.write("skip", {"leg": leg["id"], "reason": rec["note"]})
            append_csv(csv_path, hdr, [str(day), leg["id"], leg["pair"], leg["sel"], "", 0, "", "", "", rec["note"]])
            done[leg["id"]] = rec; continue
        stake = stake_for(leg, c["payout"])
        if stake <= 0:
            rec["note"] = f"倍率 {c['payout']} が下限未満で見送り"; log.say(leg["id"], rec["note"]); log.write("skip", {"leg": leg["id"], "reason": rec["note"], "contract": c})
            append_csv(csv_path, hdr, [str(day), leg["id"], leg["pair"], leg["sel"], c["payout"], 0, "", "", c["name"], rec["note"]])
            done[leg["id"]] = rec; continue
        if today_total + stake > DAILY_STAKE_CAP:
            rec["note"] = f"日次ベット上限 {DAILY_STAKE_CAP} 超過で見送り"; log.say(leg["id"], rec["note"]); log.write("skip", {"leg": leg["id"], "reason": rec["note"]})
            append_csv(csv_path, hdr, [str(day), leg["id"], leg["pair"], leg["sel"], c["payout"], 0, "", "", c["name"], rec["note"]])
            done[leg["id"]] = rec; continue
        resp = None
        for attempt in range(2):
            st, resp = rest(base, "/trading/buy", key, buy_body(c["name"], c["expiration_time"], stake))
            log.write("buy", {"leg": leg["id"], "http": st, "req": buy_body(c["name"], c["expiration_time"], stake), "body": resp})
            if resp.get("status") == "success": break
            codes = err_codes(resp); log.say(leg["id"], "buy 拒否", codes, str(resp)[:160])
            if not (set(codes) & {224, 213, 214, 216, 999}): break
            time.sleep(2)
        if resp and resp.get("status") == "success":
            d = resp.get("data") or {}; op = d.get("order_properties") or {}
            rec = {"stake": stake, "trade": str(d.get("trade")), "strike": op.get("strike"), "contract": c["name"], "payout": c["payout"]}
            today_total += stake; log.say(leg["id"], "購入", stake, "円", "trade", d.get("trade"), "strike", op.get("strike"), "倍率", c["payout"])
            append_csv(csv_path, hdr, [str(day), leg["id"], leg["pair"], leg["sel"], c["payout"], stake, d.get("trade"), op.get("strike"), c["name"], ""])
        else:
            rec["note"] = "buy 拒否 " + str(err_codes(resp)); append_csv(csv_path, hdr, [str(day), leg["id"], leg["pair"], leg["sel"], c["payout"], 0, "", "", c["name"], rec["note"]])
        done[leg["id"]] = rec; state[str(day)] = done
        json.dump(state, open(state_path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(random.uniform(4.0, 8.0))   # v1.1a: 発注を数秒ずつ分散(1 秒 1 回の制限より十分広く、開場直後の一斉発注に見えないように)
    state[str(day)] = done; json.dump(state, open(state_path, "w", encoding="utf-8"), ensure_ascii=False)
    return 0

def run_settle(account, key, out_dir, log):
    base, _ = HOSTS[account]; t0 = dt.datetime.now(UTC) - dt.timedelta(days=3)
    st, hist = rest(base, "/history/trades", key, {"reportFromTime": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "reportToTime": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    log.write("history", {"http": st, "body": hist})
    rows = ((hist.get("data") or {}).get("results") or []) if isinstance(hist, dict) else []
    path = os.path.join(out_dir, f"live_trades_{account}.csv"); seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f: seen = {r.split(",")[0] for r in f.read().splitlines()[1:]}
    hdr = ["trade_action_id", "contract", "asset", "selection", "amount", "payout_multiplier", "strike", "expiration_strike", "income", "status", "state", "start_time", "expiration_time"]
    n = 0
    for r in rows:
        tid = str(r.get("trade_action_id"))
        if tid in seen or r.get("status") not in ("Closed", "closed"): continue
        append_csv(path, hdr, [tid, r.get("contract"), r.get("asset"), r.get("selection"), r.get("amount"), r.get("payout_multiplier"), r.get("strike"),
                               r.get("expiration_strike"), r.get("income"), r.get("status"), r.get("state"), r.get("start_time"), r.get("expiration_time")]); n += 1
    log.say(f"settle: 新規 {n} 件を {os.path.basename(path)} に追記(履歴 {len(rows)} 件)"); return 0

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--settle", action="store_true"); ap.add_argument("--plan", action="store_true")
    ap.add_argument("--out", default=os.environ.get("THEOPTION_OUT") or os.path.join(HERE, "out")); a = ap.parse_args(argv)
    now = dt.datetime.now(JST); account, key = load_account(a.out)
    log = Log(os.path.join(a.out, f"live_{account}_{now:%Y%m%d}.jsonl"))
    if a.plan:
        day = now.date(); print(f"{day} ({'月火水木金土日'[day.weekday()]}) 口座={account}")
        for leg in MENU:
            if is_due_today(leg, day): print(f"  {leg['entry']} {leg['id']:14} {leg['pair']} {leg['sel']} 判定 {leg['judge']}{'(翌日)' if leg['next'] else ''} ¥{leg['stake']:,}")
        return 0
    if not key: log.say("API キーが無い"); return 2
    if not key_matches_account(account, key): log.say(f"キーが口座種別({account})に合わない → 終了"); log.write("guard", {"account": account, "iss": jwt_iss(key)}); return 3
    log.say(f"v{VERSION} 口座={account}"); keep_awake()
    return run_settle(account, key, a.out, log) if a.settle else run_entries(account, key, a.out, log, now)

if __name__ == "__main__": sys.exit(main())
