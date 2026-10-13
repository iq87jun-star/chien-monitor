# -*- coding: utf-8 -*-
"""chien IG バイナリー 窓埋めボット v0.2(research/ig_binary/README.md)。
規則: 月曜 07:00 JST の時点で「金曜終値 → 月曜最初の値」が下に窓を開けた通貨ペアだけ、IG 第 4 回号(07:00→09:00 判定)を HIGH で買う。
      v0.2: 07:00 までに窓を半分以上埋めていたペアは見送る(max_filled。夏時間だけ効く・冬時間は 07:00 が開場直後)。
検証(Dukascopy H1・中値・損益分岐 55%): 全 7 ペア合算の上昇率 2016-21 61.1% / 2022-26.5 65.6% / 2026.6-10(未使用)64.0%。

IG 証券の国内バイナリーは API 発注の可否が未確認のため、このボットは「判定・通知・結果記録」までを行い、発注は手で行う。
  signal : 月曜 07:02 JST。窓を判定し、買う通貨ペアを通知(Slack / Discord webhook)し state と log に残す。
  settle : 月曜 09:05 JST。07:00 と 09:00 の中値で勝敗を判定し、仮想損益(stake・損益分岐)を記録・通知。
  report : forward 記録(log_csv)の集計。IG の実購入価格(ig_premium 列を手で記入)があれば実際の損益分岐も出す。
  status : 設定と次回の対象日を印字。
使い方(VPS・タスクスケジューラから): python ig_gap_bot.py --config config.json --action signal|settle|report|status [--date YYYY-MM-DD] [--dry]
価格: Dukascopy 1 分足の中値(dukascopy-python)。取れなければ Yahoo 1 分足(単一価格)に落とす。
秘密(webhook URL)は config.json(git 管理外)にだけ置く。"""
import argparse, csv, datetime as dt, json, os, sys, time, urllib.request, urllib.error
VERSION = "0.2"
HERE = os.path.dirname(os.path.abspath(__file__))
UTC = dt.timezone.utc
JST = dt.timezone(dt.timedelta(hours=9))
DEFAULT_PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "EURUSD", "GBPUSD", "AUDUSD"]
LOG_COLS = ["monday", "pair", "fri_close", "mon_first", "gap_pips", "signal", "entry_mid", "exit_mid", "result", "pnl_virtual", "source", "ig_premium", "ig_result", "note"]

def pip(pair): return 0.01 if pair.endswith("JPY") else 0.0001
def fmt(pair, x): return f"{x:.3f}" if pair.endswith("JPY") else f"{x:.5f}"

def key_times(monday):
    """monday(JST の日付)の判定時刻(UTC)。entry = 07:00 JST・exit = 09:00 JST。"""
    e = dt.datetime(monday.year, monday.month, monday.day, 7, 0, tzinfo=JST).astimezone(UTC)
    return e, e + dt.timedelta(hours=2)

def weekend_gap(bars, entry_utc):
    """bars: [(t_utc, open, close)] 昇順。金曜終値 = entry の 12h 以上前の最後の close、月曜最初の値 = 直近 12h 内の最初の open。"""
    before = [b for b in bars if b[0] <= entry_utc - dt.timedelta(hours=12)]
    after = [b for b in bars if entry_utc - dt.timedelta(hours=12) < b[0] <= entry_utc + dt.timedelta(minutes=59)]
    if not before or not after: return None
    return before[-1][2], after[0][1]

def price_at(bars, t_utc, within_min=59):
    """t_utc 以降 within_min 分以内の最初の bar の open(= その時刻の値)。"""
    for b in bars:
        if t_utc <= b[0] <= t_utc + dt.timedelta(minutes=within_min): return b[1]
    return None

def filled_ratio(fri_close, mon_first, entry):
    """07:00 までに窓をどれだけ埋めたか(0 = 月曜最初の値のまま・1 = 金曜終値まで戻った・負 = さらに広げた)。"""
    return (entry - mon_first) / (fri_close - mon_first) if fri_close != mon_first else 0.0

def decide(pair, fri_close, mon_first, cfg, entry=None):
    """下窓(月曜最初の値 < 金曜終値)で、窓の大きさが min_gap_pips 以上なら HIGH。
    max_filled(既定 0.5): 07:00 時点で窓を max_filled 以上埋めていたら見送る(research/ig_binary/README.md「フィルター」)。"""
    gap = (mon_first - fri_close) / pip(pair)
    sig = "HIGH" if gap < 0 and gap <= -float(cfg.get("min_gap_pips", 0.0)) else None
    mf = cfg.get("max_filled", 0.5)
    if sig and entry is not None and mf is not None and filled_ratio(fri_close, mon_first, entry) >= float(mf): sig = None
    return sig, round(gap, 1)

def outcome(entry, exit_, direction="HIGH"):
    if entry is None or exit_ is None: return None
    if exit_ == entry: return "draw"
    return "win" if (exit_ > entry) == (direction == "HIGH") else "lose"

def pnl_virtual(result, stake, breakeven):
    """国内バイナリー: 1 枚 1,000 円払い・購入価格 = 1,000 × 損益分岐。stake 円分を買ったときの損益。"""
    if result == "win": return round(stake * (1 / breakeven - 1))
    if result == "lose": return -int(stake)
    return 0

# ---------------- price sources ----------------
class Dukascopy:
    name = "dukascopy"
    def bars(self, pair, start, end):
        import dukascopy_python as dk
        from dukascopy_python import instruments as I
        grp = "MAJORS" if pair in ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "NZDUSD") else "CROSSES"
        ins = getattr(I, f"INSTRUMENT_FX_{grp}_{pair[:3]}_{pair[3:]}")
        s, e = start.replace(tzinfo=None), end.replace(tzinfo=None)
        b = dk.fetch(ins, dk.INTERVAL_MIN_1, dk.OFFER_SIDE_BID, s, e); a = dk.fetch(ins, dk.INTERVAL_MIN_1, dk.OFFER_SIDE_ASK, s, e)
        j = b.index.intersection(a.index)
        out = []
        for t in j:
            tt = t.to_pydatetime(); tt = tt.replace(tzinfo=UTC) if tt.tzinfo is None else tt.astimezone(UTC)
            out.append((tt, (b.at[t, "open"] + a.at[t, "open"]) / 2, (b.at[t, "close"] + a.at[t, "close"]) / 2))
        return out

class Yahoo:
    name = "yahoo"
    def bars(self, pair, start, end):
        u = f"https://query2.finance.yahoo.com/v8/finance/chart/{pair}%3DX?interval=1m&period1={int(start.timestamp())}&period2={int(end.timestamp())}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15))["chart"]["result"][0]
        q = d["indicators"]["quote"][0]; out = []
        for ts, o, c in zip(d.get("timestamp") or [], q["open"], q["close"]):
            if o is not None and c is not None: out.append((dt.datetime.fromtimestamp(ts, UTC), float(o), float(c)))
        return out

def fetch_bars(cfg, pair, start, end, sources=None):
    for src in sources or [Dukascopy(), Yahoo()]:
        if src.name not in cfg.get("price_sources", ["dukascopy", "yahoo"]): continue
        try:
            b = src.bars(pair, start, end)
            if b: return b, src.name
        except Exception as e:
            print(f"[{src.name}] {pair}: {e}", file=sys.stderr)
    return [], None

# ---------------- notify ----------------
def notify(cfg, text, dry=False):
    url = cfg.get("webhook_url")
    if dry or cfg.get("transport", "dry") == "dry" or not url: print("[notify]", text); return "dry"
    body = {"content": text} if cfg.get("notify_format") == "discord" else {"text": text}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r: return str(r.status)
        except urllib.error.HTTPError as e: return f"HTTP {e.code}"
        except Exception as e: err = e; time.sleep(3)
    return f"ERR {err}"

# ---------------- state / log ----------------
class State:
    def __init__(self, path): self.path = path; self.d = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True); json.dump(self.d, open(self.path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

def log_path(cfg): return cfg.get("log_csv") or os.path.join(HERE, "out", "ig_gap_log.csv")

def append_log(cfg, row):
    p = log_path(cfg); os.makedirs(os.path.dirname(p) or ".", exist_ok=True); new = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new: w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_COLS})

# ---------------- actions ----------------
def monday_of(day): return day - dt.timedelta(days=day.weekday())

def do_signal(cfg, monday, st, dry=False, sources=None):
    key = monday.isoformat()
    if os.path.exists(os.path.join(HERE, "HALT")): print("HALT"); return
    if st.d.get(key, {}).get("signaled"): print("already signaled"); return
    entry, _ = key_times(monday); rec = {"signaled": True, "pairs": {}}
    for pair in cfg.get("pairs", DEFAULT_PAIRS):
        bars, src = [], None
        for i in range(int(cfg.get("retries", 4))):   # 開場直後は 1 分足の到着が遅れることがある
            bars, src = fetch_bars(cfg, pair, entry - dt.timedelta(hours=72), entry + dt.timedelta(minutes=5), sources)
            if weekend_gap(bars, entry) and price_at(bars, entry): break
            time.sleep(0 if dry else 30)
        g = weekend_gap(bars, entry); px = price_at(bars, entry)
        if not g or px is None:
            rec["pairs"][pair] = {"signal": None, "note": "no_price"}; continue
        sig, gap = decide(pair, g[0], g[1], cfg, px)
        rec["pairs"][pair] = {"signal": sig, "gap_pips": gap, "filled": round(filled_ratio(g[0], g[1], px), 2), "fri_close": g[0], "mon_first": g[1], "entry_mid": px, "source": src}
    st.d[key] = rec; st.save()
    buys = [(p, v) for p, v in rec["pairs"].items() if v.get("signal")]
    stake = int(cfg.get("stake", 1000))
    if buys:
        lines = [f"🔵 IG 窓埋め {key}(月)第 4 回号 07:00→09:00 判定 / 各 {stake:,} 円"] + [f"  {p} HIGH(窓 {v['gap_pips']:+.1f} pips・基準 {fmt(p, v['entry_mid'])})" for p, v in buys]
        lines.append("  ※ 購入価格(1 枚あたり)を log の ig_premium 列に記入")
    else:
        lines = [f"💤 IG 窓埋め {key}(月): 下窓なし → 見送り"]
    skipped = [p for p, v in rec["pairs"].items() if v.get("note") == "no_price"]
    if skipped: lines.append(f"  価格取得失敗: {', '.join(skipped)}")
    print("\n".join(lines)); notify(cfg, "\n".join(lines), dry)

def do_settle(cfg, monday, st, dry=False, sources=None):
    key = monday.isoformat(); rec = st.d.get(key) or {}
    if not rec.get("signaled") or rec.get("settled"): print("nothing to settle"); return
    _, exit_t = key_times(monday); stake = int(cfg.get("stake", 1000)); be = float(cfg.get("breakeven", 0.55)); total = 0; lines = []
    for pair, v in rec["pairs"].items():
        if v.get("note") == "no_price": append_log(cfg, dict(monday=key, pair=pair, note="no_price")); continue
        ex = None
        if v.get("signal"):
            for i in range(int(cfg.get("retries", 4))):
                bars, _ = fetch_bars(cfg, pair, exit_t - dt.timedelta(minutes=5), exit_t + dt.timedelta(minutes=10), sources)
                ex = price_at(bars, exit_t, within_min=10)
                if ex is not None: break
                time.sleep(0 if dry else 30)
        res = outcome(v["entry_mid"], ex) if v.get("signal") else None
        pv = pnl_virtual(res, stake, be) if res else ""
        if res: total += pv; lines.append(f"  {pair} {res}({fmt(pair, v['entry_mid'])} → {fmt(pair, ex)})")
        elif v.get("signal"): lines.append(f"  {pair} 判定価格なし")
        append_log(cfg, dict(monday=key, pair=pair, fri_close=v["fri_close"], mon_first=v["mon_first"], gap_pips=v["gap_pips"], signal=v.get("signal") or "",
                             entry_mid=v["entry_mid"], exit_mid=ex if ex is not None else "", result=res or "", pnl_virtual=pv, source=v.get("source", "")))
    rec["settled"] = True; rec["pnl_virtual"] = total; st.save()
    if lines:
        msg = "\n".join([f"🧾 IG 窓埋め {key} 結果(仮想・損益分岐 {be:.0%}・各 {stake:,} 円): {total:+,} 円"] + lines)
        print(msg); notify(cfg, msg, dry)

def summarize(rows, be=0.55, stake=1000):
    """forward 記録の集計。ig_premium(1 枚あたりの購入価格・円)があればそれを損益分岐に使った実損益も出す。"""
    t = [r for r in rows if r.get("signal") == "HIGH" and r.get("result") in ("win", "lose")]
    n = len(t); w = sum(r["result"] == "win" for r in t)
    out = dict(n=n, wins=w, wr=round(w / n, 4) if n else None, pnl_virtual=sum(int(float(r["pnl_virtual"] or 0)) for r in t))
    real = [r for r in t if r.get("ig_premium")]
    if real:
        prem = [float(r["ig_premium"]) for r in real]
        out["ig_n"] = len(real); out["ig_breakeven"] = round(sum(prem) / len(prem) / 1000, 4)
        res = lambda r: r.get("ig_result") or r["result"]
        out["ig_pnl"] = round(sum((1000 - float(r["ig_premium"])) * stake / float(r["ig_premium"]) if res(r) == "win" else -stake for r in real))
    return out

def do_report(cfg):
    p = log_path(cfg)
    rows = list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
    s = summarize(rows, float(cfg.get("breakeven", 0.55)), int(cfg.get("stake", 1000)))
    print(json.dumps(s, ensure_ascii=False)); return s

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--action", required=True, choices=["signal", "settle", "report", "status"])
    ap.add_argument("--date", default=None, help="対象週の日付(JST)。既定は今日 → その週の月曜"); ap.add_argument("--dry", action="store_true", help="通知を印字のみにする"); a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8")) if os.path.exists(a.config) else {}
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(JST).date()
    monday = monday_of(day); st = State(cfg.get("state_json") or os.path.join(HERE, "out", "state.json"))
    if a.action == "status":
        print(f"ig_gap_bot {VERSION} transport={cfg.get('transport', 'dry')} monday={monday} pairs={cfg.get('pairs', DEFAULT_PAIRS)} stake={cfg.get('stake', 1000)} breakeven={cfg.get('breakeven', 0.55)} state={st.d.get(monday.isoformat())}"); return
    if a.action in ("signal", "settle") and day.weekday() != 0 and not a.date: print("not monday"); return
    {"signal": lambda: do_signal(cfg, monday, st, a.dry), "settle": lambda: do_settle(cfg, monday, st, a.dry), "report": lambda: do_report(cfg)}[a.action]()

if __name__ == "__main__": main()
