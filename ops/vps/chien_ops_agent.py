# -*- coding: utf-8 -*-
"""chien 運用エージェント(VPS 側・Windows・Python 3.11)— docs/317 段階 1

各 MT5 端末に順に接続し、
  1) 約定履歴 → ポジション単位に組み立てた CSV(MT5 の「取引履歴レポート」xlsx と同じ列。research/forward/mt5_report.parse_csv が読む)
  2) 現在の建玉
  3) 口座スナップショット(balance / equity / margin)の追記ログ
  4) 端末ログ(MQL5/Logs)から EA の重要行([HALT] [BAL GUARD] [DAILY STOP] [EXPIRY] [PROFIT LOCK] [INIT ...] [Mon ENTRY] 等)
を `out_root/<account>/` に書き出す。out_root を Google Drive の同期フォルダ(例 G:\\マイドライブ\\chien_ops)にすると、
研究側(Claude セッション)の Routine が毎朝それを読んで乖離監視・台帳更新・ダイジェストを出す。

使い方:
  python chien_ops_agent.py --config terminals.json [--since 2026-08-01] [--out G:\\マイドライブ\\chien_ops]
  terminals.json の書式は terminals.example.json。password は端末が既にログイン済みなら省略可。

依存: pip install MetaTrader5 pandas
注意: MetaTrader5 パッケージは一度に 1 端末しか接続できないので、端末ごとに initialize → 取得 → shutdown を繰り返す。
      端末は起動していなくても path から自動起動される(初回はログイン情報が必要)。
"""
import os, sys, json, time, glob, argparse, datetime as dt
import pandas as pd
try: sys.stdout.reconfigure(errors="replace")
except Exception: pass
try:
    import chien_deploy   # docs/317 段階 2(同じフォルダ。無ければ棚卸し/配備は行わない)
except Exception:
    chien_deploy = None

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 パッケージが無い: pip install MetaTrader5"); sys.exit(2)

MANIFEST = None
MARKERS = ("[HALT]", "[BAL GUARD]", "[DAILY STOP]", "[EXPIRY]", "[PROFIT LOCK]", "[TRAIL", "[INIT", "[Mon ENTRY]", "[Mon SKIP]", "[Mon TIME EXIT]",
           "[Hold ENTRY]", "[Sess ENTRY]", "[Roll ENTRY]", "[v4 ENTRY]", "[CLOSE ALL", "[NOTIFY]", "SIZE SANITY", "銘柄解決", "解決できず")
DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT, DEAL_ENTRY_OUT_BY = 0, 1, 2, 3


def ts(v):
    return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).strftime("%Y.%m.%d %H:%M:%S")   # 端末の時刻は「サーバー時刻の Unix 秒」なので utcfromtimestamp でサーバー時刻に戻る


def build_positions(deals, orders_by_pos):
    """約定(in/out)をポジション単位に組み立て、mt5_report.parse の pos と同じ列で返す。"""
    rows = {}
    for d in deals:
        if d.type not in (0, 1):            # 0=BUY 1=SELL。残高操作(2)などは除外
            continue
        pid = d.position_id
        r = rows.setdefault(pid, dict(ticket=str(pid), symbol=d.symbol, type="", volume=0.0, open_price=0.0, open_time=None, close_time=None,
                                      close_px_vol=0.0, close_vol=0.0, commission=0.0, swap=0.0, profit=0.0, comment="", sl=0.0, tp=0.0, magic=d.magic, sl_hit=False))
        r["commission"] += float(d.commission); r["swap"] += float(d.swap)
        if d.entry in (DEAL_ENTRY_IN, DEAL_ENTRY_INOUT) and r["open_time"] is None:
            r["open_time"] = d.time; r["open_price"] = float(d.price); r["volume"] = float(d.volume); r["type"] = ("buy" if d.type == 0 else "sell")
            r["comment"] = str(d.comment or "")
        if d.entry in (DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY, DEAL_ENTRY_INOUT) and d.entry != DEAL_ENTRY_IN:
            if d.entry == DEAL_ENTRY_INOUT and r["open_time"] == d.time:
                continue
            r["close_time"] = max(r["close_time"] or 0, d.time); r["close_px_vol"] += float(d.price) * float(d.volume); r["close_vol"] += float(d.volume)
            r["profit"] += float(d.profit)
            c = str(d.comment or "")
            if c.startswith("[sl") or c.startswith("sl "): r["sl_hit"] = True
            if c.startswith("[tp") or c.startswith("tp "): r["tp_hit"] = True
    out = []
    for pid, r in rows.items():
        if r["open_time"] is None or r["close_time"] is None or r["close_vol"] <= 0:
            continue
        o = orders_by_pos.get(pid)
        if o is not None:
            r["sl"] = float(getattr(o, "sl", 0.0) or 0.0); r["tp"] = float(getattr(o, "tp", 0.0) or 0.0)
        out.append(dict(open_time=ts(r["open_time"]), ticket=r["ticket"], symbol=r["symbol"], type=r["type"], volume=r["volume"], open_price=r["open_price"],
                        sl=r["sl"], tp=r["tp"], close_time=ts(r["close_time"]), close_price=r["close_px_vol"] / r["close_vol"], commission=r["commission"],
                        swap=r["swap"], profit=r["profit"], comment=r["comment"], magic=r["magic"], sl_hit=r["sl_hit"], tp_hit=r.get("tp_hit", False)))
    cols = ["open_time", "ticket", "symbol", "type", "volume", "open_price", "sl", "tp", "close_time", "close_price", "commission", "swap", "profit", "comment", "magic", "sl_hit", "tp_hit"]
    df = pd.DataFrame(out, columns=cols)
    if len(df): df = df.sort_values("open_time")
    return df


def scan_logs(data_path, days):
    """MQL5/Logs/YYYYMMDD.log(UTF-16)から重要行を抜く。"""
    out = []
    for i in range(days):
        day = (dt.date.today() - dt.timedelta(days=i)).strftime("%Y%m%d")
        for sub in ("MQL5\\Logs", "logs"):
            p = os.path.join(data_path, sub, day + ".log")
            if not os.path.exists(p): continue
            try:
                txt = open(p, encoding="utf-16", errors="ignore").read()
            except Exception:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            for line in txt.splitlines():
                if any(m in line for m in MARKERS):
                    out.append(dict(file=f"{sub}/{day}.log", line=line.strip()[:400]))
    return pd.DataFrame(out)


def run_terminal(t, since, out_root, log_days):
    name = t["name"]; acct = str(t["account"]); d = os.path.join(out_root, acct); os.makedirs(d, exist_ok=True)
    kw = dict(path=t["path"], timeout=60000)
    if t.get("login"): kw.update(login=int(t["login"]), server=t.get("server", ""), password=t.get("password", ""))
    if t.get("portable"): kw["portable"] = True
    if not mt5.initialize(**kw):
        err = mt5.last_error(); print(f"[{name}] initialize 失敗 {err}")
        return dict(account=acct, name=name, ok=False, error=str(err), time=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat())
    try:
        ai = mt5.account_info(); ti = mt5.terminal_info()
        if ai is None or str(ai.login) != acct:
            print(f"[{name}] 口座不一致: 端末 {getattr(ai, 'login', None)} / 設定 {acct}")
            return dict(account=acct, name=name, ok=False, error="account mismatch", time=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat())
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        # 1) 約定 → ポジション
        deals = mt5.history_deals_get(dt.datetime.strptime(since, "%Y-%m-%d"), now + dt.timedelta(days=2)) or []
        pids = sorted({dd.position_id for dd in deals if dd.type in (0, 1)})
        orders_by_pos = {}
        for pid in pids:
            os_ = mt5.history_orders_get(position=pid) or []
            if os_: orders_by_pos[pid] = os_[0]
        pos = build_positions(deals, orders_by_pos)
        pos.to_csv(os.path.join(d, "positions.csv"), index=False, encoding="utf-8-sig")
        # 生の約定も残す(監査用)
        if deals:
            pd.DataFrame([dd._asdict() for dd in deals]).to_csv(os.path.join(d, "deals_raw.csv"), index=False, encoding="utf-8-sig")
        # 2) 建玉
        op = mt5.positions_get() or []
        pd.DataFrame([dict(ticket=p.ticket, symbol=p.symbol, type=("buy" if p.type == 0 else "sell"), volume=p.volume, open_time=ts(p.time), open_price=p.price_open,
                           sl=p.sl, tp=p.tp, price_current=p.price_current, swap=p.swap, profit=p.profit, magic=p.magic, comment=p.comment) for p in op]
                     ).to_csv(os.path.join(d, "open_positions.csv"), index=False, encoding="utf-8-sig")
        # 3) スナップショット(追記)
        snap = dict(time_utc=now.strftime("%Y-%m-%d %H:%M:%S"), login=ai.login, server=ai.server, currency=ai.currency, balance=ai.balance, equity=ai.equity,
                    margin=ai.margin, margin_free=ai.margin_free, floating=ai.profit, open_positions=len(op), company=ai.company)
        sp = os.path.join(d, "equity_log.csv")
        pd.DataFrame([snap]).to_csv(sp, mode="a", header=not os.path.exists(sp), index=False, encoding="utf-8-sig")
        # 4) ログ
        # docs/317 段階 2: 端末のチャート/EA 棚卸し・コンパイル・(manifest で許可された口座のみ)配備
        dep = None
        if chien_deploy is not None and ti is not None:
            try:
                dep = chien_deploy.run(t["path"], ti.data_path, acct, d, MANIFEST)
                att = dep.get("inventory", {}).get("attached", [])
                print(f"  棚卸し: チャート {len(dep.get('inventory', {}).get('charts', []))} 本 / EA {len(att)} 本: " + "; ".join(f"{a['ea']}@{a['symbol']}" for a in att)[:300])
                for a2, cc in (dep.get("compiled") or {}).items():
                    for k, v in cc.items(): print(f"  コンパイル[{a2}] {k[:50]}: {'OK' if v.get('ok') else 'NG'} {'' if v.get('ok') else str(v.get('log'))[:200]}")
                for a2, pr in (dep.get("profiles") or {}).items(): print(f"  プロファイル[{a2}]: {pr.get('profile') or pr.get('error')} {pr.get('made')}")
                if dep.get("apply"): print(f"  配備: {dep['apply']}")
            except Exception as ex:
                print(f"  棚卸し/配備 例外 {ex!r}")
        lg = scan_logs(ti.data_path, log_days) if ti is not None else pd.DataFrame()
        if lg.empty: lg = pd.DataFrame(columns=["file", "line"])
        lg.to_csv(os.path.join(d, "ea_log_extract.csv"), index=False, encoding="utf-8-sig")
        st = dict(account=acct, name=name, ok=True, time=now.isoformat(), balance=ai.balance, equity=ai.equity, open_positions=len(op),
                  attached_eas=[f"{a['ea']}@{a['symbol']}" for a in (dep or {}).get("inventory", {}).get("attached", [])],
                  deploy=({k: v for k, v in dep.items() if k in ("compiled", "apply")} if dep else None),
                  closed_positions=int(len(pos)), since=since, data_path=(ti.data_path if ti else ""), log_lines=int(len(lg)),
                  halts=int(lg.line.str.contains(r"\[HALT\]|\[BAL GUARD\]|\[DAILY STOP\]|\[EXPIRY\]|\[PROFIT LOCK\]").sum()) if len(lg) else 0,
                  last_init=(lg[lg.line.str.contains(r"\[INIT")].line.iloc[-1] if len(lg) and lg.line.str.contains(r"\[INIT").any() else ""))
        print(f"[{name}] ok balance={ai.balance:.2f} equity={ai.equity:.2f} 建玉={len(op)} 決済済={len(pos)} ログ{len(lg)}行")
        return st
    finally:
        mt5.shutdown()


def find_terminals():
    """標準的な場所から terminal64.exe を探す。"""
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"), r"C:\MT5", r"C:\chien\mt5"]
    out = []
    # 1) 起動中の terminal64.exe(どこに置かれていても捕まえる・v1.3)
    try:
        import subprocess
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | Select-Object -ExpandProperty ExecutablePath"], capture_output=True, text=True, timeout=60)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line and os.path.exists(line) and line not in out: out.append(line)
    except Exception as ex:
        print(f"[discover] プロセス列挙失敗 {ex!r}")
    # 2) 標準的な場所 + デスクトップ/ダウンロード/他ドライブ直下(深さ 2)
    home = os.path.expanduser("~")
    roots += [os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop"), os.path.join(home, "OneDrive", "デスクトップ"), os.path.join(home, "Downloads")]
    roots += [f"{d}:\\" for d in "DEFGH" if os.path.isdir(f"{d}:\\")]
    for r in roots:
        if not r or not os.path.isdir(r): continue
        try: subs = sorted(os.listdir(r))
        except Exception: continue
        for d in subs:
            for cand in (os.path.join(r, d, "terminal64.exe"), os.path.join(r, d, "MT5", "terminal64.exe")):
                if os.path.exists(cand) and cand not in out: out.append(cand)
    return out


def discover(config_path, paths=None, out_root=None, since="2026-08-01"):
    """各端末に path だけで接続(ログイン済みの口座を読む)→ terminals.json を自動生成。既存の password は引き継ぐ。"""
    paths = paths or find_terminals()
    old = {}
    if os.path.exists(config_path):
        try:
            for t in json.load(open(config_path, encoding="utf-8")).get("terminals", []): old[str(t.get("account"))] = t
        except Exception: pass
    terms = []; failed = []
    print(f"端末候補 {len(paths)} 本")
    for p in paths:
        ok = mt5.initialize(path=p, timeout=90000)
        if not ok:
            failed.append(dict(path=p, error=str(mt5.last_error()))); print(f"  × {p}: {mt5.last_error()}"); continue
        try:
            ai = mt5.account_info()
            if ai is None or not ai.login:
                failed.append(dict(path=p, error="not logged in")); print(f"  × {p}: 未ログイン"); continue
            acct = str(ai.login); prev = old.get(acct, {})
            terms.append(dict(name=f"{ai.company.split()[0] if ai.company else 'MT5'}_{acct}", account=int(acct), path=p, login=int(acct), server=ai.server,
                              password=prev.get("password", ""), enabled=True, currency=ai.currency, balance=ai.balance))
            print(f"  ○ {p} → 口座 {acct} ({ai.company} / {ai.server}) balance={ai.balance:.0f} {ai.currency}")
        finally:
            mt5.shutdown()
        time.sleep(1)
    for p in failed:   # 未ログイン端末は雛形行を残す(ユーザーが login/password を記入)
        terms.append(dict(name="UNKNOWN_" + os.path.basename(os.path.dirname(p["path"])).replace(" ", "_"), account=0, path=p["path"], login=0, server="", password="", enabled=False, note=p["error"]))
    cfg = dict(_comment="chien_ops_agent --discover が生成。enabled=false の行は端末にログインしてから再実行するか、login/password を記入して enabled=true に。",
               out_root=out_root or (old and json.load(open(config_path, encoding="utf-8")).get("out_root")) or os.path.join(os.path.dirname(os.path.abspath(config_path)), "out"),
               since=since, terminals=terms)
    json.dump(cfg, open(config_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"terminals.json を書き出し: 接続 {len(terms) - len(failed)} / 未接続 {len(failed)} → {config_path}")
    return len(failed) == 0 and len(terms) > 0


def write_diag(out_root, script_dir):
    """自己診断を out_root/_diag/ に書く(docs/317 §5b)。タスクが動かない・Drive に届かない原因を、ユーザーに schtasks や
    agent.log を貼ってもらわずに研究側(毎朝の Routine)が読めるようにする。失敗しても本体の結果には影響させない。"""
    import subprocess
    d = os.path.join(out_root, "_diag"); os.makedirs(d, exist_ok=True)
    def run(cmd):
        try:
            b = subprocess.run(cmd, capture_output=True, timeout=60).stdout
            for enc in ("cp932", "utf-8"):
                try: return b.decode(enc)
                except Exception: pass
            return b.decode("utf-8", errors="replace")
        except Exception as e: return f"ERR {e!r}"
    try: lines = open(os.path.join(script_dir, "agent.log"), encoding="utf-8", errors="replace").read().splitlines()[-80:]
    except Exception as e: lines = [f"agent.log 読めず {e!r}"]
    open(os.path.join(d, "agent_tail.txt"), "w", encoding="utf-8").write("\n".join(lines))
    open(os.path.join(d, "task.txt"), "w", encoding="utf-8").write(run(["schtasks", "/query", "/tn", "chien_ops_agent", "/v", "/fo", "list"]))
    ps = ("$b=Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; 'battery_status=' + $(if($b){$b.BatteryStatus}else{'none'}); "
          "'drive_process=' + ((Get-Process GoogleDriveFS -ErrorAction SilentlyContinue | Measure-Object).Count); "
          "'uptime_min=' + [int]((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes")
    host = (f"written_utc={dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()}\npython={sys.executable}\nscript={script_dir}\nout_root={out_root}\n"
            + run(["powershell", "-NoProfile", "-Command", ps]))
    open(os.path.join(d, "host.txt"), "w", encoding="utf-8").write(host)


class _Tee:
    """stdout/stderr を agent.log にも書く(タスクの cmd リダイレクトは引用符の扱いで失敗したため、自前で記録する)。"""
    def __init__(self, stream, path):
        self.s = stream
        try:
            if os.path.exists(path) and os.path.getsize(path) > 2_000_000:
                tail = open(path, encoding="utf-8", errors="replace").read().splitlines()[-2000:]
                open(path, "w", encoding="utf-8").write("\n".join(tail) + "\n")
            self.f = open(path, "a", encoding="utf-8", errors="replace")
        except Exception: self.f = None
    def write(self, x):
        try: self.s.write(x)
        except Exception: pass
        if self.f:
            try: self.f.write(x); self.f.flush()
            except Exception: pass
    def flush(self):
        try: self.s.flush()
        except Exception: pass


def main():
    _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")
    sys.stdout = _Tee(sys.stdout, _log); sys.stderr = _Tee(sys.stderr, _log)
    print(f"\n==== {dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()} UTC agent 1.7 ====")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "terminals.json"))
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--out", default="")
    ap.add_argument("--log-days", type=int, default=3)
    ap.add_argument("--no-deploy", action="store_true", help="棚卸し・コンパイル・配備を行わない")
    ap.add_argument("--discover", action="store_true", help="端末を自動検出して terminals.json を生成(口座はログイン済み端末から読む)")
    ap.add_argument("--paths", nargs="*", default=None, help="--discover で使う terminal64.exe のパス(省略=標準の場所を走査)")
    a = ap.parse_args()
    if a.discover:
        sys.exit(0 if discover(a.config, a.paths, a.out or None, a.since) else 1)
    cfg = json.load(open(a.config, encoding="utf-8"))
    out_root = a.out or cfg.get("out_root") or os.path.join(os.path.dirname(os.path.abspath(a.config)), "out")
    os.makedirs(out_root, exist_ok=True)
    global MANIFEST
    MANIFEST = None
    if chien_deploy is not None and not a.no_deploy:
        try: MANIFEST = chien_deploy.load_manifest(cfg.get("branch", "claude/prop-trading-new-methods-a8y3l1")); print(f"配備 manifest v{MANIFEST.get('version')} を取得")
        except Exception as ex: print(f"配備 manifest 取得失敗 {ex!r}(棚卸しのみ)")
    status = []
    for t in cfg["terminals"]:
        if not t.get("enabled", True): continue
        try:
            status.append(run_terminal(t, cfg.get("since", a.since), out_root, a.log_days))
        except Exception as e:
            print(f"[{t.get('name')}] 例外 {e!r}"); status.append(dict(account=str(t.get("account")), name=t.get("name"), ok=False, error=repr(e), time=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat()))
        time.sleep(2)
    json.dump(dict(generated_utc=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(), agent_version="1.7", terminals=status), open(os.path.join(out_root, "status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for s in status if s.get("ok")); print(f"完了 {ok}/{len(status)} 端末 → {out_root}")
    try: write_diag(out_root, os.path.dirname(os.path.abspath(__file__)))
    except Exception as e: print(f"_diag 書き出し失敗 {e!r}")


if __name__ == "__main__":
    main()
