#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theoption 本番メニューの自動発注 v1.5(既定はお試し口座。実口座は to_config.json の二重オプトインが要る)。
メニュー: theoption_validation/README.md 追補31裁定(事前登録4脚 + AUDJPY 02:00 プール脚、DD予算40万円換算、月期待 +61,160円)。
      上位10セル(v1.3)はウォークフォワードで選抜バイアス≈61%と判明したため実口座メニューから外し、紙上追跡に戻した。
      v1.5(追補34裁定): 仲値脚 = ゴトー日(5・10・15・20・25・月末、土日・銀行休業日は前倒し)の 09:55:00 JST に USDJPY/EURJPY/GBPJPY の
      FE|15M LOW(判定 10:10)を各 7,000 円。建て遅延に敏感(1 分遅れで −3pp)なので、09:54:35 から契約を先読みし 09:55:01 に 1.2 秒間隔で発注する。
動作(タスク chien_theoption_live_*: 月 06:58/09:58/12:58/13:58/15:58/17:58/20:58、火 00:58/23:58、水 01:58、毎日 22:58 に起動 → 直後の定刻の脚だけ実行して終了。
      日付をまたぐ定刻(火 23:58 起動 → 水 00:00 建て)は翌日の脚として扱う):
  0. 起動タスクに 毎日 09:54(live_0955)を追加。ゴトー日でなければ「脚は無い」で終了。
  1. ガード: 口座種別に合うキー(お試し= JWT iss が TheOptionDemo)。health → 残高 ≥ 今回のベット合計。
  2. 定刻(HH:MM:10 JST)に contracts ストリームを 20 秒集め、「銘柄 | FE | * | HIGHLOW | HIGH/LOW」で判定時刻が一致する契約を選ぶ
     (期間ラベルは問わない。無ければ「契約なし」で見送り=判定時刻が未確認の脚を安全に扱う)。
  3. 倍率規則(追補17): 1H・15M は 1.85 未満・22H/23H は 1.90 未満なら見送り、2.0 以上ならベット 1.5 倍(上限 20 万円)。
  4. 成行で購入(/trading/buy)。1 秒に 1 回。_diag/live_state.json で同じ日・同じ脚の二重発注を防ぐ。
  5. 記録: out/live_<口座>_<日付>.jsonl、out/live_entries_<口座>.csv(date,strategy_id,pair,direction,payout_actual,stake,trade_id,strike,note)。
     --settle で /history/trades を引いて out/live_trades_<口座>.csv に結果(income 等)を追記(週次突合用)。
使い方: python to_live.py            # 定刻の脚を実行(タスクから)
        python to_live.py --settle   # 直近 3 日の取引結果を取り込む(毎日 06:40 のタスク)
        python to_live.py --plan     # 今日これから実行する脚を表示して終了(発注しない)
"""
import argparse, asyncio, base64, csv, datetime as dt, json, os, random, sys, time, urllib.request, urllib.error
VERSION = "1.5"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc; JST = dt.timezone(dt.timedelta(hours=9))
HOSTS = {"demo": ("https://apidemo.theoption.com/v1", "wss://gatewaydemo.theoption.com/v1/ws"),
         "real": ("https://api.theoption.com/v1", "wss://gateway.theoption.com/v1/ws")}
MAX_STAKE = 200000; SCAN_SECS = 20; DAILY_STAKE_CAP = 120000   # 1 日のベット合計の上限(月曜 72,700 + ゴトー日の仲値 21,000 = 93,700。倍率 2.0 の 1.5 倍が重なると後の脚が見送りになる)
FAST_PRESCAN_SECS = 25; FAST_BUY_DELAY = 1.0; FAST_GAP = 1.2   # v1.5: 15M 脚は定刻の 25 秒前から契約を先読みし、定刻 +1 秒に 1.2 秒間隔で発注
# 確定メニュー(追補18)。entry = JST の定刻、judge = 判定時刻 JST(next=翌日)、wds = 曜日(0=月)、months = 対象月(None=全月)
MENU = [
 # v1.4 (2026-10-31 追補31裁定): 事前登録4脚(追補18・23、10年フルのミッド再判定) + AUDJPY 02:00 プール脚(追補29、曜日・ペア横断で成立する因子)。
 #   DD予算40万円換算(追補23のDD30万配分 ×1.33、100円丸め)。v1.3 の勝率上位10はウォークフォワードで実力がインサンプルの約4割と判明し、紙上追跡に降格。
 #   next=False の脚は同日 06:00 判定(深夜建て)。wds は「建てる日」の曜日(火〜金 02:00 建て = 月〜木セッション末尾)。
 dict(id="EURJPY_N6",   pair="EURJPY", sel="HIGH", entry="07:00", judge="06:00", next=True,  stake=21300, wds=[0], months=None, kind="23H"),
 dict(id="AUDJPY_N6",   pair="AUDJPY", sel="HIGH", entry="07:00", judge="06:00", next=True,  stake=22700, wds=[0], months=None, kind="23H"),
 dict(id="NZDJPY_N6",   pair="NZDJPY", sel="HIGH", entry="07:00", judge="06:00", next=True,  stake=18700, wds=[0], months=None, kind="23H"),
 dict(id="EURGBP_N6L",  pair="EURGBP", sel="LOW",  entry="23:00", judge="06:00", next=True,  stake=10000, wds=[0,1,2,4], months=[1,4,5,7,8,9,10,11], kind="23H"),
 dict(id="AUDJPY_02",   pair="AUDJPY", sel="HIGH", entry="02:00", judge="06:00", next=False, stake=4800,  wds=[1,2,3,4], months=None, kind="23H"),   # 火〜金 02:00 建て→同日 06:00(月〜木セッション)
 # v1.5 (2026-10-31 追補34裁定): 仲値後の反落。ゴトー日(gotobi=True: 土日・銀行休業日は直前の営業日に前倒し)の 09:55 建て→10:10 判定 LOW、15M FE 1.85。
 #   10年ミッド(FXCM M1) USDJPY 62.6 / EURJPY 64.8 / GBPJPY 62.8%(両期間合格、年別BE割れ0〜1)。3 本の相関 +0.63〜0.71。v1.4 と合算で 月+81,294 / 最大DD 344k。
 dict(id="USDJPY_NK",   pair="USDJPY", sel="LOW",  entry="09:55", judge="10:10", next=False, stake=7000,  wds=[0,1,2,3,4], months=None, kind="15M", gotobi=True),
 dict(id="EURJPY_NK",   pair="EURJPY", sel="LOW",  entry="09:55", judge="10:10", next=False, stake=7000,  wds=[0,1,2,3,4], months=None, kind="15M", gotobi=True),
 dict(id="GBPJPY_NK",   pair="GBPJPY", sel="LOW",  entry="09:55", judge="10:10", next=False, stake=7000,  wds=[0,1,2,3,4], months=None, kind="15M", gotobi=True),
]
MIN_PAYOUT = {"1H": 1.85, "15M": 1.85, "23H": 1.90}; BOOST_PAYOUT = 2.0; BOOST_MULT = 1.5

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

# ---- ゴトー日と日本の銀行休業日(v1.5) ----
def _equinox(y, which):   # 春分・秋分の近似式(1980〜2099 年で実用上一致)
    return int((20.8431 if which == "spring" else 23.2488) + 0.242194 * (y - 1980) - (y - 1980) // 4)

def jp_bank_holidays(y):
    """その年の銀行休業日(祝日・振替休日・国民の休日・12/31〜1/3)。法改正は 2019〜2021 の特例まで反映。"""
    import calendar
    H = {dt.date(y, m, d) for m, d in [(1, 1), (2, 11), (4, 29), (5, 3), (5, 4), (5, 5), (8, 11), (11, 3), (11, 23)]}
    if y >= 2020: H.add(dt.date(y, 2, 23))
    if y <= 2018: H.add(dt.date(y, 12, 23))
    H.add(dt.date(y, 3, _equinox(y, "spring"))); H.add(dt.date(y, 9, _equinox(y, "autumn")))
    def nth_mon(m, n):
        d = dt.date(y, m, 1); d += dt.timedelta(days=(7 - d.weekday()) % 7); return d + dt.timedelta(days=7 * (n - 1))
    H |= {nth_mon(1, 2), nth_mon(7, 3), nth_mon(9, 3), nth_mon(10, 2)}
    if y == 2019: H |= {dt.date(2019, 4, 30), dt.date(2019, 5, 1), dt.date(2019, 5, 2), dt.date(2019, 10, 22)}
    if y == 2020: H -= {nth_mon(7, 3), nth_mon(10, 2), dt.date(2020, 8, 11)}; H |= {dt.date(2020, 7, 23), dt.date(2020, 7, 24), dt.date(2020, 8, 10)}
    if y == 2021: H -= {nth_mon(7, 3), nth_mon(10, 2), dt.date(2021, 8, 11)}; H |= {dt.date(2021, 7, 22), dt.date(2021, 7, 23), dt.date(2021, 8, 8), dt.date(2021, 8, 9)}
    for h in sorted(H):   # 振替休日
        if h.weekday() == 6:
            d = h + dt.timedelta(days=1)
            while d in H: d += dt.timedelta(days=1)
            H.add(d)
    a = nth_mon(9, 3); b = dt.date(y, 9, _equinox(y, "autumn"))
    if (b - a).days == 2: H.add(a + dt.timedelta(days=1))   # 国民の休日
    H |= {dt.date(y, 1, 2), dt.date(y, 1, 3), dt.date(y, 12, 31)}
    return H

_HOL = {}
def is_bizday(day):
    if day.weekday() >= 5: return False
    if day.year not in _HOL: _HOL[day.year] = jp_bank_holidays(day.year)
    return day not in _HOL[day.year]

_GOTOBI = {}
def gotobi_days(y):
    """その年のゴトー日(5・10・15・20・25・月末。土日・銀行休業日は直前の営業日に前倒し)。"""
    import calendar
    if y not in _GOTOBI:
        out = set()
        for m in range(1, 13):
            for d in (5, 10, 15, 20, 25, calendar.monthrange(y, m)[1]):
                dd = dt.date(y, m, d)
                while not is_bizday(dd): dd -= dt.timedelta(days=1)
                out.add(dd)
        _GOTOBI[y] = out
    return _GOTOBI[y]

def is_gotobi(day): return day in gotobi_days(day.year) or day in gotobi_days(day.year + 1)   # 1/5 前倒しが前年 12 月末に入る場合も拾う

def is_due_today(leg, day):
    if leg.get("gotobi") and not is_gotobi(day): return False
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
    """contracts フレーム列から、銘柄・HIGH/LOW・判定時刻(UTC)が一致する Open の HIGHLOW 契約を選ぶ。期間ラベルは問わない。
    15M 脚は定刻前に先読みするため、開場前の status(Unknown 等)も許す(Closed/Expired だけ除く)。"""
    want = judge_utc(leg, day); best = None; fast = leg["kind"] == "15M"
    for fr in frames:
        if fr.get("type") != "update": continue
        c = contract_json(fr.get("values")) or {}
        name = c.get("name") or str(fr.get("key", "")).split("|20")[0]; parts = name.split("|")
        if len(parts) < 5 or parts[0] != leg["pair"] or parts[1] != "FE" or parts[3] != "HIGHLOW" or parts[4] != leg["sel"]: continue
        if fast:
            if str(c.get("status", "Open")) in ("Closed", "Expired", "Settled", "Cancelled"): continue
        elif c.get("status", "Open") not in ("Open", "Opened"): continue
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
    try: cfg = json.load(open(os.path.join(HERE, "to_config.json"), encoding="utf-8-sig"))   # v1.3a: to_setup.ps1(PS 5.1 の Set-Content UTF8)は BOM 付きで書く。utf-8 だと読めず黙ってお試しに戻っていた
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
    fast = legs[0]["kind"] == "15M"; entry0 = jst(day, legs[0]["entry"])
    if fast:   # v1.5: 先読み(定刻 −25 秒から 24 秒)→ 定刻 +1 秒に発注。1 分遅れると勝率が 3pp 落ちる脚のため
        sleep_until(entry0 - dt.timedelta(seconds=FAST_PRESCAN_SECS)); scan_secs = FAST_PRESCAN_SECS - 1
    else:
        sleep_until(entry0 + dt.timedelta(seconds=10)); scan_secs = SCAN_SECS
    try: frames = asyncio.run(scan_contracts(wss, key, scan_secs))
    except Exception as e: frames = []; log.write("error", repr(e)); log.say("contracts 購読に失敗:", repr(e))
    log.write("scan", {"n": len(frames)})
    if fast: sleep_until(entry0 + dt.timedelta(seconds=FAST_BUY_DELAY))
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
        for attempt in range(3 if fast else 2):
            st, resp = rest(base, "/trading/buy", key, buy_body(c["name"], c["expiration_time"], stake), timeout=8 if fast else 15)
            log.write("buy", {"leg": leg["id"], "http": st, "req": buy_body(c["name"], c["expiration_time"], stake), "body": resp, "t_jst": dt.datetime.now(JST).strftime("%H:%M:%S.%f")[:-3]})
            if resp.get("status") == "success": break
            codes = err_codes(resp); log.say(leg["id"], "buy 拒否", codes, str(resp)[:160])
            if fast: time.sleep(1.0); continue   # 開場直後の拒否(未開場など)は 1 秒後に再試行
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
        time.sleep(FAST_GAP if fast else random.uniform(4.0, 8.0))   # v1.1a: 発注を数秒ずつ分散。v1.5 の 15M 脚は 1.2 秒間隔(1 秒 1 回の制限内で最短)
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
        day = now.date(); print(f"{day} ({'月火水木金土日'[day.weekday()]}) 口座={account} {'ゴトー日' if is_gotobi(day) else ''}")
        for leg in MENU:
            if is_due_today(leg, day): print(f"  {leg['entry']} {leg['id']:14} {leg['pair']} {leg['sel']} 判定 {leg['judge']}{'(翌日)' if leg['next'] else ''} ¥{leg['stake']:,}")
        return 0
    if not key: log.say("API キーが無い"); return 2
    if not key_matches_account(account, key): log.say(f"キーが口座種別({account})に合わない → 終了"); log.write("guard", {"account": account, "iss": jwt_iss(key)}); return 3
    log.say(f"v{VERSION} 口座={account}"); keep_awake()
    return run_settle(account, key, a.out, log) if a.settle else run_entries(account, key, a.out, log, now)

if __name__ == "__main__": sys.exit(main())
