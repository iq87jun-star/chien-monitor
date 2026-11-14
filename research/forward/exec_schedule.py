# -*- coding: utf-8 -*-
"""docs/322 Q100(工学): 配備の予定表を deploy_manifest + EA の既定入力から生成し、実口座(ops_inbox/<口座>/positions.csv)と週次で照合して建て損ねを 1 行で報告する。
手書きの SCHEDULE(forward/exec_gap.py)を置き換える。
  予定: Mon FX レグ = 月曜 × InpMonHoursUTC のショット数(JPY レグは InpJpHolidayMondays、AUD/NZD レグは InpAuNzHolidayMondays で除外)。
        Mon 指数レグ = 月曜 × 1(米国現物寄り単発・InpMonSkipDates で除外)。Roll(InpSessEnable) = InpSessDaysUTC の曜日 × 各レグ 1(InpSessSkipDates・金利差門 InpRollRates/InpRollMinCarryPp で除外)。
        Hold / GER40 ブレイク / v4 は予定本数なし(連続・条件付き)。
  実績: positions.csv の open_time(サーバ EET)→ UTC 日付、comment の RF(I)Mon_/RFRoll_/RFSess_ で族と銘柄を判定。
使い方: cd research && python3 forward/exec_schedule.py [週の月曜 YYYY-MM-DD(UTC)・既定 = 今週(月曜の朝は前週)] [--inbox ops_inbox] [--manifest ../ops/config/deploy_manifest.json] [--json]
戻り(標準出力 1 行目): 「建て損ね なし(予定 N 本・実 N 本)」または「建て損ね: 口座 族 銘柄 日付 予定 n 実 m; …」。"""
import os, sys, re, json, glob, datetime as dt
import pandas as pd
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.dirname(ROOT)
SERVER_TZ = ZoneInfo("EET")
IDX = {"NAS100", "US500", "GER40", "UK100", "JP225", "US30", "FR40", "US100"}
SYM_MAP = {"NDX100": "NAS100", "SPX500": "US500", "US100": "NAS100", "US100.cash": "NAS100", "US500.cash": "US500", "GER40.cash": "GER40", "USOUSD": "WTI", "USOIL": "WTI", "XTIUSD": "WTI"}
INPUT_RE = re.compile(r'^\s*input\s+(?:string|int|double|bool|long)\s+(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[^;/]+?)\s*;', re.M)

def norm_sym(s):
    s = str(s).strip()
    if s.endswith("p") and s[:-1].replace(".", "").isupper() and len(s) >= 6: s = s[:-1]      # Fintokei 接尾辞 p
    return SYM_MAP.get(s, s)

def ea_inputs(mq5_path):
    txt = open(mq5_path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in INPUT_RE.finditer(txt):
        k, v = m.group(1), m.group(2).strip()
        if v.startswith('"'): v = v[1:-1]
        out[k] = v
    return out

def _csv(s): return [x.strip() for x in str(s or "").split(",") if x.strip()]
def _dates(s): return {pd.Timestamp(x.replace(".", "-")).normalize() for x in _csv(s)}
def _legs(s):
    out = []
    for p in _csv(s):
        kv = p.split(":")
        if len(kv) >= 2:
            try: out.append((kv[0].strip(), float(kv[-1])))
            except ValueError: pass
    return out

def carry_ok(sym, inp):
    """Roll の金利差門(SHORT レグ: base−quote ≥ 門)。レートが無ければ True。"""
    rates = {}
    for p in _csv(inp.get("InpRollRates", "")):
        kv = p.split(":")
        if len(kv) == 2:
            try: rates[kv[0].strip()] = float(kv[1])
            except ValueError: pass
    thr = float(inp.get("InpRollMinCarryPp", 0) or 0)
    b, q = sym[:3], sym[3:6]
    if b not in rates or q not in rates: return True
    return (rates[b] - rates[q]) >= thr

def account_rules(manifest_path=None, mql5_dir=None):
    """manifest(apply=true)→ 口座ごとの予定規則。戻り: {acct: dict(ea, mon_fx, mon_idx, shots, jp, aunz, mon_skip, roll, roll_dows, roll_skip)}"""
    manifest_path = manifest_path or os.path.join(REPO, "ops", "config", "deploy_manifest.json"); mql5_dir = mql5_dir or os.path.join(REPO, "mql5")
    d = json.load(open(manifest_path, encoding="utf-8")); rules = {}
    for acct, cfg in d["accounts"].items():
        if acct.startswith("_") or not cfg.get("apply", False) or not str(acct).isdigit(): continue
        r = dict(ea=[], mon_fx=[], mon_idx=[], shots=0, jp=set(), aunz=set(), mon_skip=set(), roll=[], roll_dows=[], roll_skip=set())
        for e in cfg.get("ensure", []):
            p = os.path.join(mql5_dir, e["ea"])
            if not os.path.exists(p): continue
            inp = ea_inputs(p); r["ea"].append(e["ea"])
            legs = _legs(inp.get("InpMonLegs", ""))
            if legs:
                hours = _csv(inp.get("InpMonHoursUTC", "4,6,8,10")); r["shots"] = max(r["shots"], len(hours))
                for sym, w in legs:
                    (r["mon_idx"] if norm_sym(sym) in IDX else r["mon_fx"]).append(norm_sym(sym))
                r["jp"] |= _dates(inp.get("InpJpHolidayMondays", "")); r["aunz"] |= _dates(inp.get("InpAuNzHolidayMondays", "")); r["mon_skip"] |= _dates(inp.get("InpMonSkipDates", ""))
            if str(inp.get("InpSessEnable", "false")).lower() == "true":
                for p5 in _csv(inp.get("InpSessLegs", "")):
                    kv = p5.split(":")
                    if len(kv) == 5 and carry_ok(kv[0].strip(), inp): r["roll"].append(norm_sym(kv[0]))
                r["roll_dows"] = [int(x) for x in _csv(inp.get("InpSessDaysUTC", "3"))]; r["roll_skip"] |= _dates(inp.get("InpSessSkipDates", ""))
        rules[acct] = r
    return rules

def expected_week(rules, monday):
    """monday(UTC 日付)から 7 日間の予定本数。戻り: list(dict(account, fam, sym, date, n_expected))"""
    monday = pd.Timestamp(monday).normalize(); rows = []
    for acct, r in rules.items():
        for sym in r["mon_fx"]:
            skip = (monday in r["jp"] and "JPY" in sym) or (monday in r["aunz"] and (sym.startswith("AUD") or sym.startswith("NZD")))
            rows.append(dict(account=acct, fam="Mon", sym=sym, date=monday.date().isoformat(), n_expected=0 if skip else r["shots"]))
        for sym in r["mon_idx"]:
            rows.append(dict(account=acct, fam="Mon", sym=sym, date=monday.date().isoformat(), n_expected=0 if monday in r["mon_skip"] else 1))
        for off in range(7):
            day = monday + pd.Timedelta(days=off)
            if r["roll"] and (day.dayofweek + 1) % 7 in r["roll_dows"] and day not in r["roll_skip"]:   # MQL5: 0=日 … 3=水; pandas: 0=月
                for sym in r["roll"]: rows.append(dict(account=acct, fam="Roll", sym=sym, date=day.date().isoformat(), n_expected=1))
    return rows

def actual_week(inbox, monday):
    """実績: positions.csv(決済済み)+ open_positions.csv(建玉中)。同じ(口座・族・銘柄・日・時刻タグ)の複数行(分割約定)は 1 本に数える。"""
    monday = pd.Timestamp(monday).normalize(); end = monday + pd.Timedelta(days=7); keys = set()
    for p in sorted(glob.glob(os.path.join(inbox, "*", "positions.csv")) + glob.glob(os.path.join(inbox, "*", "open_positions.csv"))):
        acct = os.path.basename(os.path.dirname(p))
        if not acct.isdigit(): continue
        try: df = pd.read_csv(p)
        except Exception: continue
        if not len(df) or "open_time" not in df.columns or "comment" not in df.columns: continue
        t = pd.to_datetime(df["open_time"], format="%Y.%m.%d %H:%M:%S", errors="coerce")
        utc = t.dt.tz_localize(SERVER_TZ, nonexistent="shift_forward", ambiguous="NaT").dt.tz_convert("UTC").dt.tz_localize(None)
        for c, u in zip(df["comment"].astype(str), utc):
            if pd.isna(u) or not (monday <= u < end): continue
            m = re.match(r"RF(I?Mon|Roll|Sess|Hold|v4)_([A-Za-z0-9.]+?)(?:_h(\d+))?$", c.strip())
            if not m: continue
            fam = {"IMon": "Mon", "Sess": "Roll"}.get(m.group(1), m.group(1)); tag = m.group(3) if m.group(3) else str(u.hour)
            keys.add((acct, fam, norm_sym(m.group(2)), u.normalize().date().isoformat(), tag))
    return [dict(account=a, fam=f, sym=s_, date=d) for (a, f, s_, d, _) in sorted(keys)]

def duplicate_entries(inbox, monday):
    """二重建ての疑い: 同じ(口座・族・銘柄・日・時刻タグ)に、建て時刻が 2 秒以上離れた同量の行が 2 本以上(分割約定は同秒)。戻り: list(dict)"""
    monday = pd.Timestamp(monday).normalize(); end = monday + pd.Timedelta(days=7); out = []
    for p in sorted(glob.glob(os.path.join(inbox, "*", "positions.csv"))):
        acct = os.path.basename(os.path.dirname(p))
        if not acct.isdigit(): continue
        try: df = pd.read_csv(p)
        except Exception: continue
        if not len(df) or "open_time" not in df.columns: continue
        t = pd.to_datetime(df["open_time"], format="%Y.%m.%d %H:%M:%S", errors="coerce")
        df = df.assign(_t=t)[(t >= monday.tz_localize(SERVER_TZ).tz_convert(None) - pd.Timedelta(hours=3)) & (t < (end + pd.Timedelta(hours=3)))]
        df = df[df["comment"].astype(str).str.match(r"RF(I?Mon|Roll|Sess)_")]
        for (c, d), g in df.groupby([df["comment"].astype(str), df["_t"].dt.date]):
            if len(g) < 2: continue
            span = (g["_t"].max() - g["_t"].min()).total_seconds(); same_vol = g["volume"].round(2).nunique() == 1
            if span >= 2 and same_vol: out.append(dict(account=acct, comment=c, date=str(d), n=int(len(g)), volume=float(g["volume"].iloc[0]), span_sec=int(span)))
    return out

def check_week(monday, inbox=None, manifest=None):
    inbox = inbox or os.path.join(ROOT, "ops_inbox"); rules = account_rules(manifest)
    exp = pd.DataFrame(expected_week(rules, monday)); act = pd.DataFrame(actual_week(inbox, monday))
    if not len(exp): return dict(line="予定表が空(manifest に apply=true の口座なし)", rows=[])
    if len(act): cnt = act.groupby(["account", "fam", "sym", "date"]).size().rename("n_actual").reset_index(); exp = exp.merge(cnt, how="left", on=["account", "fam", "sym", "date"])
    else: exp["n_actual"] = 0
    exp["n_actual"] = exp["n_actual"].fillna(0).astype(int)
    have_pos = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(inbox, "*", "positions.csv"))}
    exp["recorded"] = exp["account"].isin(have_pos)
    miss = exp[(exp.n_expected > exp.n_actual) & exp.recorded]; norec = sorted(set(exp[~exp.recorded].account))
    parts = [f"{r.account} {r.fam} {r.sym} {r.date} 予定 {r.n_expected} 実 {r.n_actual}" for r in miss.itertuples()]
    line = (f"建て損ね なし(予定 {int(exp[exp.recorded].n_expected.sum())} 本・実 {int(exp[exp.recorded].n_actual.sum())} 本)" if not len(miss) else "建て損ね: " + "; ".join(parts))
    if norec: line += f" | 記録なし: {','.join(norec)}"
    dup = duplicate_entries(inbox, monday)
    if dup:
        by = {}
        for d_ in dup: by.setdefault(d_["account"], []).append(d_)
        line += " | ⚠二重建ての疑い: " + "; ".join(f"{a} {len(v)} ショット(例 {v[0]['comment']} {v[0]['n']} 本 × {v[0]['volume']} lot・{v[0]['span_sec']} 秒差)" for a, v in by.items())
    return dict(line=line, rows=exp.to_dict("records"), duplicates=dup, week=str(pd.Timestamp(monday).date()))

def expected_counts_month(rules, year, month):
    """exec_gap.py 用: 月ごとの予定本数(口座・族・銘柄)。"""
    first = pd.Timestamp(year, month, 1); mondays = pd.date_range(first - pd.Timedelta(days=first.dayofweek), first + pd.offsets.MonthEnd(0), freq="7D")
    rows = []
    for mon in mondays:
        for r in expected_week(rules, mon):
            if pd.Timestamp(r["date"]).month == month and pd.Timestamp(r["date"]).year == year: rows.append(r)
    if not rows: return pd.DataFrame(columns=["account", "fam", "sym", "n_expected"])
    return pd.DataFrame(rows).groupby(["account", "fam", "sym"]).n_expected.sum().reset_index()

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = sys.argv[1:]
    inbox = opts[opts.index("--inbox") + 1] if "--inbox" in opts else None; manifest = opts[opts.index("--manifest") + 1] if "--manifest" in opts else None
    if args: monday = pd.Timestamp(args[0])
    else:
        today = pd.Timestamp(dt.datetime.utcnow().date()); monday = today - pd.Timedelta(days=today.dayofweek)   # 今週の月曜(火〜日)。月曜の朝は前週
        if today.dayofweek == 0: monday -= pd.Timedelta(days=7)
    res = check_week(monday, inbox, manifest); print(f"[週 {res.get('week')}] {res['line']}")
    if "--json" in opts: print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        df = pd.DataFrame(res["rows"])
        if len(df): print(df[["account", "fam", "sym", "date", "n_expected", "n_actual", "recorded"]].to_string(index=False))
