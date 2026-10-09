# -*- coding: utf-8 -*-
"""chien 先物ボット v0.1(docs/336 Q117)。MFFU(Tradovate)向けに「月曜 13 UTC 建て → 同日 20 UTC 決済」の Mon 指数 日中版(docs/333〜335)を発注する。
設計: 判断(どの限月を何枚・今日は建てるか)はここで完結し、発注は transport に委ねる。transport = dry(印字のみ)/ webhook(TradersPost 形式の JSON を POST)/ tradovate(REST・未検証)。
使い方(VPS・タスクスケジューラから): python mffu_bot.py --config config.json --action entry|exit|check|status [--date YYYY-MM-DD] [--dry]
  entry : 月曜 13:00 UTC(= 22:00 JST)。CME 休場・HALT ファイル・当日既建ての場合は何もしない。
  exit  : 月曜 20:00 UTC(= 火 05:00 JST)。当日建てた分を flat にする(sentiment=flat)。
  check : 20:30 UTC。state に未決済が残っていれば exit を再送(16:10 ET の強制清算より前の最後の保険)。
  keepalive: 火曜 13:00 UTC(= 22:00 JST)。前日の月曜が休場等で建てなかった週だけ、最小 1 枚を建てて 60 秒後に決済する(sim 本口座の「7 日無取引で閉鎖」を避ける保守取引)。
  status: 設定・次回の限月・枚数を印字。
秘密(webhook URL・API キー)は config.json(git 管理外)にだけ置く。公開リポジトリには config.example.json のみ。"""
import argparse, csv, datetime as dt, json, os, sys, time, urllib.request, urllib.error
VERSION = "0.2"
HERE = os.path.dirname(os.path.abspath(__file__))
MONTH_CODES = {3: "H", 6: "M", 9: "U", 12: "Z"}
DEFAULT_SYMBOLS = {"MES": {"qty": 2, "cfd": "US500"}, "MNQ": {"qty": 1, "cfd": "NAS100"}, "MYM": {"qty": 2, "cfd": "US30"}}

def third_friday(y, m):
    d = dt.date(y, m, 15)
    while d.weekday() != 4: d += dt.timedelta(days=1)
    return d

def front_contract(root, day, roll_days=8):
    """取引日 day に使う限月。四半期限月(H/M/U/Z)の第 3 金曜が day + roll_days より後なら当該限月、そうでなければ次。
    (指数先物の出来高は満期 8 日前=前週木曜に次限月へ移る。月曜取引なので満期週の月曜は次限月になる。)"""
    y, m = day.year, day.month
    for _ in range(8):
        q = ((m - 1) // 3 + 1) * 3
        exp = third_friday(y, q)
        if exp > day + dt.timedelta(days=roll_days): return f"{root}{MONTH_CODES[q]}{y}"
        m = q + 1
        if m > 12: m, y = 1, y + 1
    raise RuntimeError("front_contract")

def load_holidays(path):
    out = set()
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("cal") in ("NYSE", "CME"): out.add(r["date"])
    return out

class State:
    def __init__(self, path): self.path = path; self.d = json.load(open(path)) if os.path.exists(path) else {}
    def save(self): os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True); json.dump(self.d, open(self.path, "w"), indent=1)

def log_row(cfg, **kw):
    p = cfg.get("log_csv") or os.path.join(HERE, "out", "mffu_log.csv"); os.makedirs(os.path.dirname(p), exist_ok=True)
    new = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["utc", "action", "contract", "qty", "transport", "result", "note"])
        w.writerow([dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), kw.get("action"), kw.get("contract"), kw.get("qty"), kw.get("transport"), kw.get("result"), kw.get("note", "")])

# ---------------- transports ----------------
class Dry:
    name = "dry"
    def __init__(self, cfg): pass
    def send(self, payload): print("[dry]", json.dumps(payload)); return "dry"

class Webhook:
    """TradersPost 形式: POST {url} に {ticker, action, quantity | sentiment:'flat'}。URL は config.webhook_url(秘密)。"""
    name = "webhook"
    def __init__(self, cfg):
        self.url = cfg.get("webhook_url");
        if not self.url: raise SystemExit("config.webhook_url が無い")
    def send(self, payload):
        body = json.dumps(payload).encode(); req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        for i in range(3):
            try:
                with urllib.request.urlopen(req, timeout=15) as r: return f"{r.status} {r.read(300).decode(errors='replace')}"
            except urllib.error.HTTPError as e: return f"HTTP {e.code} {e.read(300).decode(errors='replace')}"
            except Exception as e: err = e; time.sleep(3)
        return f"ERR {err}"

class Tradovate:
    """Tradovate REST(未検証・docs/336 §3: プロップ口座では API キーが発行されないため、現状は到達不能)。host は demo/live。"""
    name = "tradovate"
    def __init__(self, cfg):
        c = cfg.get("tradovate") or {}; self.host = c.get("host", "https://demo.tradovateapi.com/v1"); self.c = c; self.tok = None
    def _post(self, path, body, auth=True):
        h = {"Content-Type": "application/json"}
        if auth: h["Authorization"] = f"Bearer {self.tok}"
        req = urllib.request.Request(self.host + path, data=json.dumps(body).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read().decode())
    def _get(self, path):
        req = urllib.request.Request(self.host + path, headers={"Authorization": f"Bearer {self.tok}"})
        with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read().decode())
    def auth(self):
        c = self.c; r = self._post("/auth/accesstokenrequest", dict(name=c["user"], password=c["password"], appId="chien", appVersion=VERSION, cid=c["cid"], sec=c["sec"], deviceId=c.get("device_id", "chien-vps")), auth=False)
        self.tok = r["accessToken"]; return r
    def send(self, payload):
        if not self.tok: self.auth()
        acct = self._get("/account/list")[0]
        if payload.get("sentiment") == "flat":
            cid = self._get(f"/contract/find?name={payload['ticker']}")["id"]
            return json.dumps(self._post("/order/liquidateposition", dict(accountId=acct["id"], contractId=cid, admin=False, isAutomated=True)))
        return json.dumps(self._post("/order/placeorder", dict(accountSpec=acct["name"], accountId=acct["id"], action="Buy" if payload["action"] == "buy" else "Sell", symbol=payload["ticker"], orderQty=int(payload["quantity"]), orderType="Market", isAutomated=True)))

TRANSPORTS = {"dry": Dry, "webhook": Webhook, "tradovate": Tradovate}

# ---------------- decisions ----------------
def plan(cfg, day):
    """その日に建てる契約と枚数。月曜以外・休場・HALT は空。"""
    reasons = []
    if day.weekday() != 0: reasons.append("not_monday")
    if day.isoformat() in load_holidays(cfg.get("holidays_csv")): reasons.append("holiday")
    if os.path.exists(os.path.join(HERE, "HALT")): reasons.append("HALT_file")
    syms = cfg.get("symbols") or DEFAULT_SYMBOLS
    legs = [dict(root=r, contract=front_contract(r, day), qty=int(v["qty"])) for r, v in syms.items() if int(v.get("qty", 0)) > 0]
    total = sum(l["qty"] for l in legs)
    if total > int(cfg.get("max_contracts_total", 10)): reasons.append(f"max_contracts_total({total})")
    return legs, reasons

def run(cfg, action, day, transport):
    st = State(cfg.get("state_json") or os.path.join(HERE, "out", "state.json")); key = day.isoformat()
    legs, reasons = plan(cfg, day)
    if action == "status":
        print(f"mffu_bot {VERSION} transport={transport.name} day={key} legs={legs} reasons={reasons}"); return
    if action == "entry":
        if reasons: print("skip entry:", reasons); log_row(cfg, action="entry", transport=transport.name, result="skip", note=",".join(reasons)); return
        if st.d.get(key, {}).get("entered"): print("already entered today"); return
        st.d[key] = {"entered": True, "open": [], "exited": False}
        for l in legs:
            res = transport.send(dict(ticker=l["contract"], action="buy", quantity=l["qty"], time=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), extras={"bot": f"chien-mffu-{VERSION}", "leg": "MonIdxIntra"}))
            st.d[key]["open"].append(l); st.save(); log_row(cfg, action="entry", contract=l["contract"], qty=l["qty"], transport=transport.name, result=res)
        return
    if action in ("exit", "check"):
        rec = st.d.get(key) or {}
        if not rec.get("entered") or rec.get("exited"):
            if action == "exit": log_row(cfg, action=action, transport=transport.name, result="nothing_to_exit")
            print("nothing to exit"); return
        for l in rec["open"]:
            res = transport.send(dict(ticker=l["contract"], action="sell", sentiment="flat", time=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), extras={"bot": f"chien-mffu-{VERSION}", "why": action}))
            log_row(cfg, action=action, contract=l["contract"], qty=l["qty"], transport=transport.name, result=res)
        rec["exited"] = True; st.save(); return
    if action == "keepalive":
        mon = day - dt.timedelta(days=day.weekday())
        if day.weekday() != 1: print("keepalive: not tuesday"); return
        if st.d.get(mon.isoformat(), {}).get("entered"): print("keepalive: traded this week"); return
        if st.d.get(key, {}).get("keepalive"): print("keepalive: already done"); return
        if not legs: print("keepalive: no legs"); return
        root = cfg.get("keepalive_symbol", legs[0]["root"]); c = front_contract(root, day); wait = int(cfg.get("keepalive_wait_sec", 60))
        r1 = transport.send(dict(ticker=c, action="buy", quantity=1, extras={"bot": f"chien-mffu-{VERSION}", "why": "keepalive"}))
        time.sleep(wait if transport.name != "dry" else 0)
        r2 = transport.send(dict(ticker=c, action="sell", sentiment="flat", extras={"bot": f"chien-mffu-{VERSION}", "why": "keepalive"}))
        st.d.setdefault(key, {})["keepalive"] = True; st.save(); log_row(cfg, action="keepalive", contract=c, qty=1, transport=transport.name, result=f"{r1} / {r2}"); return
    raise SystemExit(f"unknown action {action}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", default=os.path.join(HERE, "config.json")); ap.add_argument("--action", required=True, choices=["entry", "exit", "check", "keepalive", "status"])
    ap.add_argument("--date", default=None, help="判断日(UTC)。既定は今日"); ap.add_argument("--dry", action="store_true", help="transport を dry に強制"); a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8")) if os.path.exists(a.config) else {}
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.utcnow().date()
    tr = TRANSPORTS["dry" if a.dry else cfg.get("transport", "dry")](cfg)
    run(cfg, a.action, day, tr)

if __name__ == "__main__": main()
