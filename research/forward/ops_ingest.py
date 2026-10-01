# -*- coding: utf-8 -*-
"""docs/317 段階 1: VPS エージェント(ops/vps/chien_ops_agent.py)の出力を取り込み、口座ごとのダイジェストを出す。

使い方: python3 forward/ops_ingest.py <取り込みディレクトリ>   (Drive の chien_ops を丸ごと落としたもの: <dir>/<account>/positions.csv 等)
出力: results/ops_digest_latest.json と標準出力の要約(Routine がそのまま報告に使う)。
  ・口座ごと: 最新 balance / equity / 建玉数 / 直近 7 日の決済損益 / SL 決済率 / ガード発動・EXPIRY・INIT の有無
  ・レグ別(コメント RFMon_ 等): 直近 30 日の建玉数と損益
  ・deviation_monitor.py は positions.csv を xlsx と同様に読めるので、逸脱検知はそちらを別途実行(python3 forward/deviation_monitor.py <dir>)。"""
import os, sys, json, glob, re, datetime as dt, warnings; warnings.filterwarnings("ignore")
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, HERE)
import mt5_report as mr
LEG_RE = re.compile(r"^RF\w*?(Mon|Hold|Roll|Sess|v4|Tsmom)[A-Za-z]*?_([A-Za-z0-9._]+?)(?:_h(\d+))?$")


def digest(d):
    acct = os.path.basename(d.rstrip("/\\")); out = dict(account=acct)
    ep = os.path.join(d, "equity_log.csv")
    if os.path.exists(ep) and os.path.getsize(ep) > 0:
        e = pd.read_csv(ep); last = e.iloc[-1]
        out.update(snapshot_utc=str(last.time_utc), balance=float(last.balance), equity=float(last.equity), open_positions=int(last.open_positions), currency=str(last.currency))
        if len(e) > 1: out["equity_24h_change"] = float(last.equity) - float(e[e.time_utc <= (pd.Timestamp(last.time_utc) - pd.Timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")].equity.iloc[-1]) if (e.time_utc <= (pd.Timestamp(last.time_utc) - pd.Timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")).any() else None
    pp = os.path.join(d, "positions.csv")
    if os.path.exists(pp):
        _, pos, *_ = mr.parse(pp)
        if len(pos):
            pos = pos.dropna(subset=["close_time"]); now = pos.close_time.max()
            w7 = pos[pos.close_time >= now - pd.Timedelta(days=7)]; w30 = pos[pos.close_time >= now - pd.Timedelta(days=30)]
            out.update(closed_total=int(len(pos)), last_close=str(now), net_7d=round(float(w7.net.sum()), 2), n_7d=int(len(w7)), net_30d=round(float(w30.net.sum()), 2))
            if "sl_hit" in pos.columns: out["sl_hit_rate_30d"] = round(float(w30.sl_hit.astype(str).str.lower().eq("true").mean()) * 100, 1) if len(w30) else None
            legs = []
            for _, r in w30.iterrows():
                m = LEG_RE.match(str(r.comment).strip())
                if m: legs.append(dict(family=m.group(1), symbol=m.group(2), net=r.net))
            if legs:
                L = pd.DataFrame(legs).groupby(["family", "symbol"]).net.agg(["size", "sum"]).round(2)
                out["legs_30d"] = {f"{a}/{b}": dict(n=int(n), net=float(s)) for (a, b), (n, s) in L.iterrows()}
    lp = os.path.join(d, "ea_log_extract.csv")
    if os.path.exists(lp) and os.path.getsize(lp) > 0:
        try: lg = pd.read_csv(lp)
        except pd.errors.EmptyDataError: lg = pd.DataFrame()
        if len(lg):
            out["alerts"] = lg[lg.line.str.contains(r"\[HALT\]|\[BAL GUARD\]|\[DAILY STOP\]|\[EXPIRY\]|\[PROFIT LOCK\]|\[TRAIL|解決できず|SIZE SANITY")].line.tail(10).tolist()
            ini = lg[lg.line.str.contains(r"\[INIT")]
            out["last_init"] = ini.line.iloc[-1][:200] if len(ini) else ""
            out["ea_names"] = sorted(set(m.group(1) for m in (re.search(r"\t(【[^\t]+?)\s*\(", l) for l in lg.line.astype(str)) if m))   # ログに出た EA 名(端末で動いている EA)
            out["init_versions"] = sorted(set(re.findall(r"\[INIT [^\]]*?v(\d+\.\d+)\]", " ".join(ini.line.astype(str)))))
            out["entries_3d"] = int(lg.line.str.contains(r"ENTRY\]").sum())
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "ops_inbox"
    st = os.path.join(root, "status.json"); status = json.load(open(st, encoding="utf-8")) if os.path.exists(st) else {}
    rows = [digest(d) for d in sorted(glob.glob(os.path.join(root, "*"))) if os.path.isdir(d) and os.path.basename(d).isdigit()]   # _diag 等は口座ではない
    res = dict(ingested_utc=dt.datetime.utcnow().isoformat(), agent_generated_utc=status.get("generated_utc"), accounts=rows,
               agent_failures=[t for t in status.get("terminals", []) if not t.get("ok")])
    os.makedirs("results", exist_ok=True); json.dump(res, open("results/ops_digest_latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"エージェント生成 {status.get('generated_utc')} / 口座 {len(rows)} / 失敗 {len(res['agent_failures'])}")
    for r in rows:
        print(f"#{r['account']}: eq {r.get('equity', float('nan')):,.0f} (bal {r.get('balance', float('nan')):,.0f}) 建玉 {r.get('open_positions', '-')} | 7日 {r.get('net_7d', '-')} ({r.get('n_7d', '-')} 本) | 30日 {r.get('net_30d', '-')} SL率 {r.get('sl_hit_rate_30d', '-')}% | 3日の建て {r.get('entries_3d', '-')} | 警告 {len(r.get('alerts', []))}")
        for a in r.get("alerts", [])[-3:]: print("   ! " + a[:160])
        if r.get("ea_names"): print("   EA:", "; ".join(n[:60] for n in r["ea_names"]), "| INIT 版:", ",".join(r.get("init_versions", [])) or "なし")
    for f in res["agent_failures"]: print(f"   × エージェント失敗 #{f.get('account')} {f.get('name')}: {f.get('error')}")


if __name__ == "__main__":
    main()
