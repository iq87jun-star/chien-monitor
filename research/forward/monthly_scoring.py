# -*- coding: utf-8 -*-
"""docs/322 Q102(工学): 実口座の月次採点(docs/179 ランブック・docs/219 様式)を ops_inbox の記録から自動実行する。
入力: ops_inbox/<口座>/positions.csv(決済済み・net = profit+commission+swap)・equity_log.csv(月初残高)・config/portfolio_current.json(口座の帳簿と倍率)。
照合先の分布: forward/portfolio_sim.legs() の帳簿系列(10.6 年・Yahoo 日足近似・コスト後)を倍率で合成した暦月リターン(余裕比例 k は含めない = 固定倍率の分布)。
判定(docs/174 §5・docs/175 §5): 月次 R<0 の連続回数、分布の下方 5% 割れの連続回数。状態は results/monthly_scoring_state.json に保持(口座・月ごとに 1 行・再実行は上書き)。
使い方: cd research && python3 forward/monthly_scoring.py [YYYY-MM ...](既定 = 前月)[--inbox ops_inbox] [--md](docs 用の表を出力)
出力: results/monthly_scoring_<YYYY-MM>.csv・標準出力に docs/219 §4 様式の表。"""
import os, sys, re, json, glob, datetime as dt
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import mt5_report as mr
ACCT_KEY = {"521100397": "FTMO 50k 521100397", "531407058": "FTMO 50k 531407058", "531343523": "宝くじ 531343523", "531466484": "1-Step 531466484", "11988011": "FN Instant 11988011",
            "14074882": "FN 14074882", "14166201": "FN 14166201", "6071612": "パール 6071612", "6104736": "ルビー 6104736", "6104739": "トパーズ 6104739"}
FAM_RE = re.compile(r"^RF(I?Mon|Roll|Sess|Hold|v4|Brk|5-S\d)")
STATE = os.path.join(ROOT, "results", "monthly_scoring_state.json")

def fam_of(c):
    m = FAM_RE.match(str(c).strip())
    if not m: return "other"
    f = m.group(1); return {"IMon": "Mon", "Sess": "Roll"}.get(f, "RF5" if f.startswith("5-") else f)

_DIST = {}
def book_monthly_dist(spec):
    """帳簿 spec({leg: mult})の暦月リターン分布(%)。"""
    key = json.dumps(spec, sort_keys=True)
    if key in _DIST: return _DIST[key]
    from forward.portfolio_sim import book
    s = book(spec); mo = s.groupby(pd.PeriodIndex(s.index, freq="M")).sum() * 100
    q = dict(p5=float(mo.quantile(.05)), p16=float(mo.quantile(.16)), p50=float(mo.quantile(.5)), p84=float(mo.quantile(.84)), p95=float(mo.quantile(.95)), mean=float(mo.mean()), n=int(len(mo)))
    _DIST[key] = q; return q

def month_balance(acct, inbox, y, m):
    """月初残高(equity_log の当月最初の balance。無ければ前月末)と月末残高。"""
    p = os.path.join(inbox, acct, "equity_log.csv")
    if not os.path.exists(p): return None, None
    e = pd.read_csv(p); e["t"] = pd.to_datetime(e.time_utc); first = pd.Timestamp(y, m, 1); last = first + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)
    cur = e[(e.t >= first) & (e.t < last)]; prev = e[e.t < first]
    b0 = float(prev.iloc[-1].balance) if len(prev) else (float(cur.iloc[0].balance) if len(cur) else None)
    b1 = float(cur.iloc[-1].balance) if len(cur) else None
    return b0, b1

def score_month(y, m, inbox="ops_inbox"):
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); acc_cfg = {a["name"]: a for a in cfg["accounts"]}
    rows = []
    for d in sorted(glob.glob(os.path.join(inbox, "*"))):
        acct = os.path.basename(d)
        if not acct.isdigit() or acct not in ACCT_KEY: continue
        pp = os.path.join(d, "positions.csv")
        if not os.path.exists(pp): continue
        _, pos, *_ = mr.parse(pp)
        if not len(pos): continue
        pos = pos.dropna(subset=["close_time"]); pos["ct"] = pd.to_datetime(pos.close_time)
        mo = pos[(pos.ct.dt.year == y) & (pos.ct.dt.month == m)]
        b0, b1 = month_balance(acct, inbox, y, m)
        net = float(mo.net.sum()) if len(mo) else 0.0; pct = (net / b0 * 100) if b0 else np.nan
        fam = mo.assign(f=mo.comment.map(fam_of)).groupby("f").net.agg(["size", "sum"]) if len(mo) else pd.DataFrame()
        fam_txt = " / ".join(f"{f} {int(r['size'])}本 {r['sum']:+.0f}" for f, r in fam.iterrows()) if len(fam) else "-"
        sl = int(mo.sl_hit.astype(str).str.lower().eq("true").sum()) if ("sl_hit" in mo.columns and len(mo)) else None
        a = acc_cfg.get(ACCT_KEY[acct], {}); spec = a.get("funded" if a.get("funded_now") else "eval", {}); q = book_monthly_dist(spec) if spec else None
        below5 = (pct < q["p5"]) if (q and not np.isnan(pct)) else None
        rows.append(dict(month=f"{y}-{m:02d}", account=acct, name=ACCT_KEY[acct], bal_start=b0, bal_end=b1, n=int(len(mo)), net=round(net, 2), pct=round(pct, 2) if not np.isnan(pct) else None,
                         families=fam_txt, sl_hits=sl, dist_p5=round(q["p5"], 2) if q else None, dist_p50=round(q["p50"], 2) if q else None, dist_p95=round(q["p95"], 2) if q else None,
                         r_neg=bool(pct < 0) if not np.isnan(pct) else None, below_p5=below5, spec=json.dumps(spec, ensure_ascii=False)))
    return pd.DataFrame(rows)

def update_state(df):
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    for r in df.itertuples():
        st.setdefault(r.account, {})[r.month] = dict(pct=r.pct, r_neg=r.r_neg, below_p5=r.below_p5)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 連続回数(採点月まで・月の並び順)
    cons = {}
    for acct, months in st.items():
        ks = sorted(months); cn = cb = 0
        for k in ks:
            v = months[k]; cn = cn + 1 if v.get("r_neg") else 0; cb = cb + 1 if v.get("below_p5") else 0
        cons[acct] = dict(r_neg_streak=cn, below_p5_streak=cb, months=len(ks))
    return cons

def md_table(df, cons):
    out = [f"| 口座 | 月初残高 | 本数 | 純損益 | 月次 % | 分布(5% / 中央 / 95%) | 判定 | 族別 |", "|---|--:|--:|--:|--:|---|---|---|"]
    for r in df.itertuples():
        c = cons.get(r.account, {}); j = []
        if r.r_neg: j.append(f"R<0(連続 {c.get('r_neg_streak', 1)})")
        if r.below_p5: j.append(f"**下方 5% 割れ(連続 {c.get('below_p5_streak', 1)})**")
        if not j: j.append("分布内・R>0" if r.pct is not None and r.pct >= 0 else "-")
        dist = f"{r.dist_p5:+.1f} / {r.dist_p50:+.1f} / {r.dist_p95:+.1f}" if r.dist_p5 is not None else "-"
        out.append(f"| {r.name} | {r.bal_start:,.0f} | {r.n} | {r.net:+,.0f} | {('%+.2f%%' % r.pct) if r.pct is not None else '-'} | {dist} | {' / '.join(j)} | {r.families} |")
    return "\n".join(out)

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = sys.argv[1:]
    inbox = opts[opts.index("--inbox") + 1] if "--inbox" in opts else "ops_inbox"
    if not args:
        t = dt.date.today().replace(day=1) - dt.timedelta(days=1); args = [f"{t.year}-{t.month:02d}"]
    for ym in args:
        y, m = int(ym[:4]), int(ym[5:7]); df = score_month(y, m, inbox)
        if not len(df): print(f"[{ym}] 記録なし"); continue
        cons = update_state(df); os.makedirs("results", exist_ok=True); df.to_csv(f"results/monthly_scoring_{ym}.csv", index=False)
        print(f"== 月次採点 {ym}(ops_inbox・分布 = 固定倍率の帳簿 10.6 年暦月)=="); print(md_table(df, cons))
        tot = df.net.sum(); print(f"合計(通貨混在のため参考): 本数 {int(df.n.sum())} | R<0 {int(df.r_neg.fillna(False).sum())} 口座 | 下方 5% 割れ {int(df.below_p5.fillna(False).sum())} 口座 | 保存 results/monthly_scoring_{ym}.csv")
