# -*- coding: utf-8 -*-
"""
edge21_emon_hold_10y.py — docs/117(事前登録)の実行: E-Mon(指数月曜LONG)の保有時間比較。
  H24(現行: 月曜open→火曜open) vs HDC(同日決済: 月曜open→月曜close)
主判定: 日足10年(2016-2025・固定窓CSV=docs/114検証と同一)。
副確認: Yahoo H1 約2年(ES=F/NQ=F/^GDAXI・9/14UTC建て)の符号整合のみ。
夜越しファイナンス感応: F0=0 / F2=2.6bps / F4=4bps per夜(H24のみ負担)。
⚠ 事前登録の後に実行。結果はdocs/118へ転記。出力: results/edge21_emon_hold_10y.json
"""
import os, sys, json, csv, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from parallel_vs_existing_compare import load_daily

EMON = ["NAS100", "US500", "GER40"]
COST = 3e-4                      # 往復(現行スリーブと同一)
FIN = {"F0": 0.0, "F2": 2.6e-4, "F4": 4.0e-4}   # per夜(H24=1夜)
H1_P1, H1_P2 = 1720483200, 1783468800   # 2024-07-09 .. 2026-07-07 UTC(Yahoo 1h上限730日内)
H1_SYMS = {"NQ=F": "NAS100", "ES=F": "US500", "^GDAXI": "GER40"}


def weekly_series(kind, cost_mult=1.0):
    """月曜リターン系列(3銘柄平均)。kind='o2o'(H24) or 'o2c'(HDC)。"""
    parts = []
    for nm in EMON:
        df = load_daily(nm)
        mon = df[df["weekday"] == 0]
        if kind == "o2o":
            r = mon["o2o"]
        else:
            r = mon["close"] / mon["open"] - 1.0
        parts.append((r - COST * cost_mult).rename(nm))
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    idx = pd.DatetimeIndex(w.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    w.index = idx
    return w


def metrics(w):
    eq = (1 + w).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = w.mean() * 52; vol = w.std() * np.sqrt(52)
    yrs = len(w) / 52.0
    cagr = (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if eq.iloc[-1] > 0 else -100
    # docs/87式: 最悪週-4% / maxDD-8% 逆算×0.8 → score=mult×平均週次
    worst = float(w.min())
    m1 = 0.04 / abs(worst) if worst < 0 else 5.0
    m2 = 0.08 / abs(dd / 100) if dd < 0 else 5.0
    mult = round(0.8 * min(m1, m2, 5.0), 2)
    return dict(net_pct=round(float(eq.iloc[-1] - 1) * 100, 1), cagr=round(float(cagr), 2),
                sharpe=round(float(mu / vol) if vol > 0 else 0, 2), maxDD=round(dd, 2),
                calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0,
                worst_week=round(worst * 100, 2), mult=mult,
                score=round(mult * float(w.mean() * 100), 4), weeks=int(len(w)))


def h1_fetch():
    out = {}
    hashes = {}
    for sym, name in H1_SYMS.items():
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
             f"?interval=1h&period1={H1_P1}&period2={H1_P2}")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read()
        hashes[name] = hashlib.sha256(raw).hexdigest()[:16]
        d = json.loads(raw)
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(ts):
            o = q["open"][i]
            if o is None:
                continue
            rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc), float(o)))
        out[name] = rows
        print(f"  H1 {name}: {len(rows)} bars")
    return out, hashes


def h1_variant(h1, hold):
    """hold='dc'(同日最終バー) or '24h'。9/14UTC建て・両shot平均・銘柄平均の週次系列。"""
    per = {}
    for name, rows in h1.items():
        byday = {}
        for t, o in rows:
            byday.setdefault(t.date(), []).append((t, o))
        rets = {}
        days = sorted(byday)
        for di, day in enumerate(days):
            if day.weekday() != 0:
                continue
            bars = byday[day]
            legs = []
            for hh in (9, 14):
                ent = [b for b in bars if b[0].hour == hh]
                if not ent:
                    continue
                t0, p0 = ent[0]
                if hold == "dc":
                    px = bars[-1][1]
                else:
                    nxt = None
                    for dj in range(di + 1, min(di + 4, len(days))):
                        cand = [b for b in byday[days[dj]] if b[0].hour >= hh]
                        allb = byday[days[dj]]
                        if cand:
                            nxt = cand[0][1]; break
                        if allb:
                            nxt = allb[-1][1]; break
                    if nxt is None:
                        continue
                    px = nxt
                legs.append(px / p0 - 1.0)
            if legs:
                rets[day] = float(np.mean(legs)) - COST
        per[name] = pd.Series(rets)
    df = pd.DataFrame(per)
    return df.mean(axis=1, skipna=True).dropna()


def main():
    # 主判定: 日足10年
    res = {}
    for tag, kind in (("H24", "o2o"), ("HDC", "o2c")):
        w = weekly_series(kind)
        w10 = w[(w.index.year >= 2016) & (w.index.year <= 2025)]
        res[tag] = {"series": w10}
        base = metrics(w10)
        for f, bps in FIN.items():
            wf = w10 - (bps if tag == "H24" else 0.0)
            res[tag][f] = metrics(wf)
        res[tag]["ref2026H1_pct"] = round(float(w[w.index.year == 2026].sum() * 100), 2)
    print("日足10年(週次520本級):")
    for tag in ("H24", "HDC"):
        for f in FIN:
            print(f"  {tag} {f}: {res[tag][f]}")
        print(f"  {tag} 2026H1参考: {res[tag]['ref2026H1_pct']}%")

    # 頑健性: IS/OOS 70:30・年次JK(F2での net差の符号)・コスト2倍(F0)
    n = len(res["H24"]["series"])
    cut = int(n * 0.7)
    rob = {}
    for f in ("F0", "F2"):
        bps = FIN[f]
        a = res["H24"]["series"] - bps; b = res["HDC"]["series"]
        rob[f] = dict(
            IS=dict(H24=metrics(a.iloc[:cut]), HDC=metrics(b.iloc[:cut])),
            OOS=dict(H24=metrics(a.iloc[cut:]), HDC=metrics(b.iloc[cut:])))
    jk = {}
    for y in range(2016, 2026):
        a = res["H24"]["series"]; b = res["HDC"]["series"]
        m = a.index.year != y
        diff_f0 = float((b[m] - a[m]).sum())
        diff_f2 = float((b[m] - (a[m] - FIN["F2"])).sum())
        jk[y] = dict(F0=round(diff_f0 * 100, 2), F2=round(diff_f2 * 100, 2))
    print("年次JK(HDC−H24 累積差% / 除外年別): ", jk)

    cost2 = {tag: metrics((weekly_series(kind, 2.0))[(weekly_series(kind, 2.0).index.year >= 2016)
                                                     & (weekly_series(kind, 2.0).index.year <= 2025)])
             for tag, kind in (("H24", "o2o"), ("HDC", "o2c"))}
    print("コスト2倍(F0):", {k: v["score"] for k, v in cost2.items()})

    # 副確認: H1 約2年
    print("H1副確認(2024-07〜2026-07・9/14UTC建て):")
    h1, h1sha = h1_fetch()
    h1res = {}
    for tag, hold in (("H24", "24h"), ("HDC", "dc")):
        s = h1_variant(h1, hold)
        h1res[tag] = dict(net_pct=round(float(s.sum() * 100), 2), weeks=int(len(s)),
                          worst_week=round(float(s.min() * 100), 2))
        print(f"  {tag}: {h1res[tag]}")

    # 決定規則(docs/117 §4)
    A = (res["HDC"]["F0"]["score"] >= 1.1 * res["H24"]["F0"]["score"]
         and res["HDC"]["F0"]["net_pct"] >= 0.9 * res["H24"]["F0"]["net_pct"]
         and cost2["HDC"]["score"] >= cost2["H24"]["score"]
         and (h1res["HDC"]["net_pct"] >= h1res["H24"]["net_pct"]))
    B = (res["HDC"]["F2"]["net_pct"] > res["H24"]["F2"]["net_pct"]
         and res["HDC"]["F2"]["calmar"] >= res["H24"]["F2"]["calmar"])
    if A:
        decision = "HDC採用(無条件)"
    elif B:
        decision = "HDC条件付き採用(夜越しコスト実測がF2級以上の業者のみ)"
    else:
        decision = "H24維持(現行24h)"
    print("決定:", decision)

    out = dict(prereg="docs/117", window_daily="2016-01..2025-12(固定窓CSV=docs/114と同一)",
               fin_scenarios_bps_per_night={k: v * 1e4 for k, v in FIN.items()},
               daily={tag: {f: res[tag][f] for f in FIN} for tag in ("H24", "HDC")},
               ref_2026H1={tag: res[tag]["ref2026H1_pct"] for tag in ("H24", "HDC")},
               robustness=rob, jackknife_excl_year=jk,
               cost2x_F0={k: v for k, v in cost2.items()},
               h1_secondary=dict(window="2024-07-09..2026-07-07", sha256=h1sha, res=h1res),
               decision=decision)
    path = os.path.join(HERE, "results", "edge21_emon_hold_10y.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
