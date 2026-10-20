# -*- coding: utf-8 -*-
"""theoption 自動売買 API の確認用プローブ v0.1(取引はしない)。
目的: 月曜朝の窓埋め(ops/ig_binary)を theoption の「期間固定(FD)・1 時間・ハイロー」で取れるかを決める 3 点を実測する。
  1. 月曜の何時(JST)から FD|1H|HIGHLOW が Opened で出るか(開場 = 夏 06:00 / 冬 07:00 JST の直後に買えるか)
  対象: FD|1H・22H・23H|HIGHLOW(① 月曜窓埋め 1H / ② Mon4 22H・23H / ③ 水曜夜の円買い 1H = 木曜 05:00〜09:00 JST)
  2. 払い戻し倍率(契約 JSON のどの欄に出るかも含めて丸ごと記録)
  3. 開場直後の判定価格(contract_data ストリームの値・取れれば)
やること: health → balance → WebSocket で contracts ストリームを購読し、届いたフレームを JSONL にそのまま保存。/buy・/sell は一切呼ばない。
使い方:
  set THEOPTION_API_KEY=<お試し用 API キー>        (Windows。キーはチャットやファイルに貼らない)
  python to_probe.py --check                         # 接続確認: health・残高・いま出ている契約を 60 秒集めて要約して終了
  python to_probe.py --until 09:30                   # 月曜朝用: 09:30 JST まで記録(タスクで 05:25 起動)
  python to_summarize.py out\\probe_YYYYMMDD.jsonl   # 記録の要約
既定はお試し環境(apidemo / gatewaydemo)。--env live は本番ホスト(キーも本番用が要る)。"""
import argparse, asyncio, datetime as dt, json, os, sys, time, urllib.request, urllib.error
VERSION = "0.3"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
JST = dt.timezone(dt.timedelta(hours=9))
HOSTS = {"demo": ("https://apidemo.theoption.com/v1", "wss://gatewaydemo.theoption.com/v1/ws"),
         "live": ("https://api.theoption.com/v1", "wss://gateway.theoption.com/v1/ws")}
TARGET_ASSETS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "EURUSD", "GBPUSD", "AUDUSD"]

def parse_name(name):
    """'USDJPY|FD|1H|HIGHLOW|HIGH[|2026_08_10_14_05_00]' → dict。区切りは '|'。固定の並びを仮定しすぎない。"""
    s = [x.strip() for x in str(name).split("|")]
    d = dict(asset=s[0] if s else "", exp=s[1] if len(s) > 1 else "", dur=s[2] if len(s) > 2 else "", product=s[3] if len(s) > 3 else "", sel="", stamp="")
    for x in s[4:]:
        if x in ("HIGH", "LOW"): d["sel"] = x
        elif x[:2].isdigit() and "_" in x: d["stamp"] = x
    return d

TARGET_DURS = ("1H", "22H", "23H")   # ① 月曜窓埋め 1H・② Mon4 → 22H/23H・③ 水曜夜の円買い 1H

def is_target(name):
    d = parse_name(name); return d["exp"] == "FD" and d["dur"].upper() in TARGET_DURS and d["product"] == "HIGHLOW" and d["asset"] in TARGET_ASSETS

# v0.3: 木曜朝(= 水曜 20〜24 UTC・③ 水曜夜の円買い)も記録する。設定済みの VPS にもタスクを足すため、実行のたびに無ければ登録する。
EXTRA_TASKS = [("chien_theoption_thursday", "THU", "04:55", "thursday")]

def ensure_tasks():
    if os.name != "nt": return []
    import subprocess
    runner = os.path.join(HERE, "to_run.ps1"); made = []
    if not os.path.exists(runner): return []
    for name, day, at, mode in EXTRA_TASKS:
        if subprocess.run(["schtasks", "/Query", "/TN", name], capture_output=True).returncode == 0: continue
        tr = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{runner}" -Mode {mode}'
        r = subprocess.run(["schtasks", "/Create", "/SC", "WEEKLY", "/D", day, "/ST", at, "/TN", name, "/TR", tr, "/F"], capture_output=True, text=True)
        made.append((name, r.returncode)); print("タスク登録:", name, day, at, "ok" if r.returncode == 0 else r.stderr.strip())
    return made

def contract_json(values):
    """values.contract は JSON 文字列。壊れていれば None。"""
    c = (values or {}).get("contract")
    if isinstance(c, dict): return c
    try: return json.loads(c) if c else None
    except (TypeError, ValueError): return None

def rest(base, path, key, timeout=15):
    req = urllib.request.Request(base + path, data=b"{}", method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try: return e.code, json.loads(body)
        except ValueError: return e.code, {"raw": body[:500]}
    except Exception as e: return None, {"error": repr(e)}

class Recorder:
    """フレームを JSONL に保存し、対象契約の初出を数える。テストからも使う(ネットワーク不要)。"""
    def __init__(self, path):
        self.path = path; self.first_seen = {}; self.n = 0; self.data_subs = {}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    def write(self, kind, obj):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"recv_utc": dt.datetime.now(UTC).isoformat(), "kind": kind, "frame": obj}, ensure_ascii=False) + "\n")
    def on_frame(self, fr):
        """戻り値: 新しく見つかった対象契約名のリスト(contract_data の購読候補)。"""
        self.n += 1; self.write("ws", fr); new = []
        if fr.get("type") == "update":
            key = fr.get("key", ""); c = contract_json(fr.get("values")) or {}
            name = c.get("name") or key.split("|20")[0]
            if is_target(name) and c.get("status", "Opened") == "Opened" and name not in self.first_seen:
                self.first_seen[name] = dt.datetime.now(UTC); new.append(name)
        return new

async def ws_session(ws_url, key, rec, until_utc, want_data, check_secs):
    import websockets
    hdr = {"Authorization": "Bearer " + key}
    try: conn = websockets.connect(ws_url, additional_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)
    except TypeError: conn = websockets.connect(ws_url, extra_headers=hdr, open_timeout=20, ping_interval=20, max_size=None)   # websockets < 14
    async with conn as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 30)); rec.write("ws", first)
        if first.get("type") != "ready": print("最初のフレームが ready ではない:", first); return
        rid = 1
        await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contracts"}))
        t_end = time.time() + check_secs if check_secs else None
        while dt.datetime.now(UTC) < until_utc and (t_end is None or time.time() < t_end):
            try: raw = await asyncio.wait_for(ws.recv(), 30)
            except asyncio.TimeoutError: continue
            try: fr = json.loads(raw)
            except ValueError: rec.write("raw", raw[:2000]); continue
            for name in rec.on_frame(fr):
                print(dt.datetime.now(JST).strftime("%m/%d %H:%M:%S"), "初出", name, flush=True)
                if want_data and len(rec.data_subs) < 20:   # 判定価格を見るため。購読の書式は公開資料が要約のみ → 応答(エラー含む)も記録
                    rid += 1; rec.data_subs[name] = rid
                    await ws.send(json.dumps({"type": "subscribe", "reqId": str(rid), "stream": "contract_data", "key": name}))

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--env", choices=list(HOSTS), default="demo")
    ap.add_argument("--until", default="09:30", help="JST の終了時刻 HH:MM(当日。過ぎていれば翌日)")
    ap.add_argument("--check", action="store_true", help="60 秒だけ集めて要約して終了"); ap.add_argument("--no-data", action="store_true")
    ap.add_argument("--out", default=os.environ.get("THEOPTION_OUT") or os.path.join(HERE, "out")); a = ap.parse_args(argv)
    key = os.environ.get("THEOPTION_API_KEY", "").strip()
    if not key: print("環境変数 THEOPTION_API_KEY が無い(お試し用キーを入れる)"); return 2
    try: ensure_tasks()
    except Exception as e: print("タスク確認に失敗(記録は続ける):", repr(e))
    base, wss = HOSTS[a.env]; now = dt.datetime.now(JST)
    path = os.path.join(a.out, f"probe_{a.env}_{now:%Y%m%d_%H%M}.jsonl"); rec = Recorder(path)
    st, h = rest(base, "/trading/health", key); rec.write("health", {"http": st, "body": h}); print("health:", st, json.dumps(h, ensure_ascii=False)[:300])
    if st != 200 or h.get("status") == "fail":
        print("health 失敗。エラー 13 ならキーと環境(demo/live)の組み合わせを確認"); write_summary(path, rec); return 1
    st, b = rest(base, "/wallet/balance", key); rec.write("balance", {"http": st, "body": b}); print("balance:", st, json.dumps(b, ensure_ascii=False)[:300])
    hh, mm = map(int, a.until.split(":")); until = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if until <= now: until += dt.timedelta(days=1)
    until_utc = until.astimezone(UTC); backoff = 5
    print(f"記録先 {path} / 終了 {until:%m/%d %H:%M} JST / 取引はしない", flush=True)
    while dt.datetime.now(UTC) < until_utc:
        try:
            asyncio.run(ws_session(wss, key, rec, until_utc, not a.no_data, 60 if a.check else 0)); backoff = 5
            if a.check: break
        except Exception as e:
            rec.write("error", repr(e)); print("WS 切断:", repr(e), f"{backoff}s 後に再接続", flush=True); time.sleep(backoff); backoff = min(backoff * 2, 120)
    print(f"フレーム {rec.n} 件・対象契約の初出 {len(rec.first_seen)} 件")
    write_summary(path, rec)
    return 0

def write_summary(path, rec):
    """要約を <記録>.summary.txt に、実行状況を <out>/_diag/last_run.txt に書く(Drive 同期先に置けばチャット側から読める)。"""
    import io, contextlib, to_summarize
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): to_summarize.report(path)
    txt = buf.getvalue(); print(txt)
    with open(path[:-6] + ".summary.txt", "w", encoding="utf-8") as f: f.write(txt)
    d = os.path.join(os.path.dirname(path), "_diag"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "last_run.txt"), "w", encoding="utf-8") as f:
        f.write(f"version={VERSION}\nfinished_jst={dt.datetime.now(JST):%Y-%m-%d %H:%M:%S}\nfile={os.path.basename(path)}\nframes={rec.n}\ntargets={len(rec.first_seen)}\npython={sys.executable}\n")

if __name__ == "__main__": sys.exit(main())
