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

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 パッケージが無い: pip install MetaTrader5"); sys.exit(2)

MARKERS = ("[HALT]", "[BAL GUARD]", "[DAILY STOP]", "[EXPIRY]", "[PROFIT LOCK]", "[TRAIL", "[INIT", "[Mon ENTRY]", "[Mon SKIP]", "[Mon TIME EXIT]",
           "[Hold ENTRY]", "[Sess ENTRY]", "[Roll ENTRY]", "[v4 ENTRY]", "[CLOSE ALL", "[NOTIFY]", "SIZE SANITY", "銘柄解決", "解決できず")
DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT, DEAL_ENTRY_OUT_BY = 0, 1, 2, 3


def ts(v):
    return dt.datetime.utcfromtimestamp(int(v)).strftime("%Y.%m.%d %H:%M:%S")   # 端末の時刻は「サーバー時刻の Unix 秒」なので utcfromtimestamp でサーバー時刻に戻る


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
    df = pd.DataFrame(out)
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
        return dict(account=acct, name=name, ok=False, error=str(err), time=dt.datetime.utcnow().isoformat())
    try:
        ai = mt5.account_info(); ti = mt5.terminal_info()
        if ai is None or str(ai.login) != acct:
            print(f"[{name}] 口座不一致: 端末 {getattr(ai, 'login', None)} / 設定 {acct}")
            return dict(account=acct, name=name, ok=False, error="account mismatch", time=dt.datetime.utcnow().isoformat())
        now = dt.datetime.utcnow()
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
        lg = scan_logs(ti.data_path, log_days) if ti is not None else pd.DataFrame()
        lg.to_csv(os.path.join(d, "ea_log_extract.csv"), index=False, encoding="utf-8-sig")
        st = dict(account=acct, name=name, ok=True, time=now.isoformat(), balance=ai.balance, equity=ai.equity, open_positions=len(op),
                  closed_positions=int(len(pos)), since=since, data_path=(ti.data_path if ti else ""), log_lines=int(len(lg)),
                  halts=int(lg.line.str.contains(r"\[HALT\]|\[BAL GUARD\]|\[DAILY STOP\]|\[EXPIRY\]|\[PROFIT LOCK\]").sum()) if len(lg) else 0,
                  last_init=(lg[lg.line.str.contains(r"\[INIT")].line.iloc[-1] if len(lg) and lg.line.str.contains(r"\[INIT").any() else ""))
        print(f"[{name}] ok balance={ai.balance:.2f} equity={ai.equity:.2f} 建玉={len(op)} 決済済={len(pos)} ログ{len(lg)}行")
        return st
    finally:
        mt5.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "terminals.json"))
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--out", default="")
    ap.add_argument("--log-days", type=int, default=3)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    out_root = a.out or cfg.get("out_root") or os.path.join(os.path.dirname(os.path.abspath(a.config)), "out")
    os.makedirs(out_root, exist_ok=True)
    status = []
    for t in cfg["terminals"]:
        if not t.get("enabled", True): continue
        try:
            status.append(run_terminal(t, cfg.get("since", a.since), out_root, a.log_days))
        except Exception as e:
            print(f"[{t.get('name')}] 例外 {e!r}"); status.append(dict(account=str(t.get("account")), name=t.get("name"), ok=False, error=repr(e), time=dt.datetime.utcnow().isoformat()))
        time.sleep(2)
    json.dump(dict(generated_utc=dt.datetime.utcnow().isoformat(), agent_version="1.0", terminals=status), open(os.path.join(out_root, "status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for s in status if s.get("ok")); print(f"完了 {ok}/{len(status)} 端末 → {out_root}")


if __name__ == "__main__":
    main()
