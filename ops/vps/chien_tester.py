# -*- coding: utf-8 -*-
"""chien_tester 1.0 — docs/322 Q94: MT5 ストラテジーテスターの自動実行(docs/362)。
テスター専用の端末(terminals.json の "tester" エントリ)で `terminal64.exe /config:tester.ini` を起動し、EA のバックテストを走らせ、
レポート(htm)とログを Drive `chien_ops/_tester/<日付>_<EA>_<銘柄>/` に置く。本番端末(稼働中のプロセスがある path)では決して走らせない。
使い方(VPS / 手元 PC・Python 3.12):
  python chien_tester.py --config terminals.json --ea "<mql5/ の EA ファイル名>" --symbol GBPJPY --period H1 --from 2024-01-01 --to 2026-08-31 [--deposit 100000] [--set inputs.set] [--branch ...]
terminals.json に足す(password は端末がログイン済みなら省略可・ファイルは git 管理外):
  "tester": {"path": "C:\\chien\\mt5\\_tester\\terminal64.exe", "login": 0, "server": "", "password": "", "currency": "USD", "leverage": 100}
制約: 自動売買は起動しない([Experts] を書かない)。本番端末の data_path は触らない。パスワードはログ・Drive に書かない。"""
import os, sys, json, time, shutil, argparse, datetime as dt, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import chien_deploy
VERSION = "1.0"
PERIODS = {"M1": "M1", "M5": "M5", "M15": "M15", "M30": "M30", "H1": "H1", "H4": "H4", "D1": "D1"}

def is_portable(terminal_path):
    return os.path.isdir(os.path.join(os.path.dirname(terminal_path), "MQL5"))

def data_path_for(terminal_path):
    """ポータブルなら端末フォルダ、そうでなければ chien_deploy の棚卸しと同じ AppData の data_path を使う(id は terminal.ini から)。"""
    if is_portable(terminal_path): return os.path.dirname(terminal_path)
    raise SystemExit("テスター端末はポータブル構成(terminal64.exe と同じフォルダに MQL5)にしてください(docs/362 §2)")

def write_ini(path, ea_rel, symbol, period, d_from, d_to, deposit, currency, leverage, report, login=None, server=None, password=None, set_file=None):
    lines = []
    if login: lines += ["[Common]", f"Login={login}", f"Server={server}"] + ([f"Password={password}"] if password else []) + [""]
    lines += ["[Tester]", f"Expert={ea_rel}", f"Symbol={symbol}", f"Period={PERIODS[period]}", "Model=1", "ExecutionMode=0", "Optimization=0",
              f"FromDate={d_from.replace('-', '.')}", f"ToDate={d_to.replace('-', '.')}", "ForwardMode=0", f"Deposit={deposit}", f"Currency={currency}", f"Leverage=1:{leverage}",
              f"Report={report}", "ReplaceReport=1", "ShutdownTerminal=1", "Visual=0"]
    if set_file: lines.append(f"ExpertParameters={set_file}")
    with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")

def run_tester(cfg, ea_file, symbol, period, d_from, d_to, deposit, set_file=None, branch="claude/prop-trading-new-methods-a8y3l1", out_root=None, timeout=3600):
    t = cfg.get("tester")
    if not t: raise SystemExit("terminals.json に tester エントリがありません(docs/362 §2)")
    tp = t["path"]; dp = data_path_for(tp)
    live_paths = {x["path"] for x in cfg.get("terminals", []) if x.get("enabled", True)}
    if tp in live_paths: raise SystemExit("tester.path が本番端末と同じです。専用のポータブル端末を使ってください")
    if chien_deploy.terminal_pids(tp): raise SystemExit("テスター端末が起動中です(前回の実行が終わっていない)。終了を待ってから再実行")
    # 1) EA を取得してコンパイル(chien_deploy と同じ手順・MQL5\Experts\chien\)
    c = chien_deploy.compile_ea(tp, dp, branch, ea_file)
    if not c.get("ok"): return dict(ok=False, stage="compile", log=c.get("log"))
    ea_rel = "chien\\" + ea_file[:-4]   # [Tester] Expert= は Experts\ からの相対・拡張子なし
    stamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M"); safe = "".join(ch for ch in ea_file[:-4] if ch not in '\\/:*?"<>|')[:60]
    report = f"chien_{stamp}_{symbol}"; ini = os.path.join(dp, "chien_tester.ini")
    sp = None
    if set_file:
        sp = os.path.join(dp, "MQL5", "Profiles", "Tester", os.path.basename(set_file)); os.makedirs(os.path.dirname(sp), exist_ok=True); shutil.copyfile(set_file, sp); sp = os.path.basename(set_file)
    write_ini(ini, ea_rel, symbol, period, d_from, d_to, deposit, t.get("currency", "USD"), t.get("leverage", 100), report, t.get("login") or None, t.get("server"), t.get("password") or None, sp)
    # 2) 起動(/portable・/config)→ ShutdownTerminal=1 で自動終了するのを待つ
    args = [tp, "/portable", f"/config:{ini}"]; t0 = time.time()
    p = subprocess.Popen(args, cwd=os.path.dirname(tp))
    try: rc = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        chien_deploy.stop_terminal(tp); return dict(ok=False, stage="timeout", sec=int(time.time() - t0))
    # 3) レポートとログを集める
    rep = os.path.join(dp, report + ".htm"); outs = {}
    out_root = out_root or cfg.get("out_root"); od = os.path.join(out_root, "_tester", f"{stamp}_{safe}_{symbol}"); os.makedirs(od, exist_ok=True)
    if os.path.exists(rep): shutil.copyfile(rep, os.path.join(od, "report.htm")); outs["report"] = os.path.join(od, "report.htm")
    logs = sorted([os.path.join(dp, "Tester", "logs", f) for f in os.listdir(os.path.join(dp, "Tester", "logs"))] if os.path.isdir(os.path.join(dp, "Tester", "logs")) else [])
    if logs: shutil.copyfile(logs[-1], os.path.join(od, "tester.log")); outs["log"] = os.path.join(od, "tester.log")
    try:
        s = open(ini, encoding="utf-8").read().splitlines(); s = [l for l in s if not l.startswith("Password=")]   # パスワードは残さない
        open(os.path.join(od, "tester.ini"), "w", encoding="utf-8").write("\n".join(s) + "\n")
    except Exception: pass
    meta = dict(version=VERSION, ea=ea_file, symbol=symbol, period=period, from_=d_from, to=d_to, deposit=deposit, set=sp, rc=rc, sec=int(time.time() - t0), report_found=bool(outs.get("report")), utc=dt.datetime.utcnow().isoformat())
    json.dump(meta, open(os.path.join(od, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return dict(ok=bool(outs.get("report")), stage="done", out_dir=od, **meta)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); ap.add_argument("--ea", required=True); ap.add_argument("--symbol", required=True); ap.add_argument("--period", default="H1")
    ap.add_argument("--from", dest="d_from", required=True); ap.add_argument("--to", dest="d_to", required=True); ap.add_argument("--deposit", type=int, default=100000); ap.add_argument("--set", default=None)
    ap.add_argument("--branch", default="claude/prop-trading-new-methods-a8y3l1"); ap.add_argument("--timeout", type=int, default=3600); a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    r = run_tester(cfg, a.ea, a.symbol, a.period, a.d_from, a.d_to, a.deposit, a.set, a.branch, timeout=a.timeout)
    print(json.dumps({k: v for k, v in r.items() if k != "log"}, ensure_ascii=False)); 
    if r.get("log"): print(r["log"])
    sys.exit(0 if r.get("ok") else 1)

if __name__ == "__main__": main()
