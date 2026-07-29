# -*- coding: utf-8 -*-
"""
edge22_emon_night_10y.py — docs/119(事前登録)の実行: E-Mon夜間限定エントリー。
  HNO(月曜close→火曜open) vs H24(現行: 月曜open→火曜open)
主判定: 日足10年(2016-2025・固定窓CSV)。月曜特異性プラセボ(火〜金のc2o)必須。
副確認: Yahoo H1 約2年(GER=最終バー→翌初バー / US=20:00UTC→翌13:00UTC)。
⚠ 事前登録の後に実行。結果はdocs/120へ転記。出力: results/edge22_emon_night_10y.json
"""
import os, sys, json, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from parallel_vs_existing_compare import load_daily
from edge21_emon_hold_10y import metrics, EMON, COST, H1_P1, H1_P2, H1_SYMS


def weekly(kind, weekday=0, cost_mult=1.0):
    """kind: 'o2o'(H24) / 'c2o'(HNO) / 'o2c'(HDC参考)。weekday: 0=月曜(プラセボで1-4)。"""
    parts = []
    for nm in EMON:
        df = load_daily(nm).copy()
        df["c2o"] = df["open"].shift(-1) / df["close"] - 1.0
        sub = df[df["weekday"] == weekday]
        r = sub[kind] if kind != "o2c" else (sub["close"] / sub["open"] - 1.0)
        parts.append((r - COST * cost_mult).rename(nm))
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    idx = pd.DatetimeIndex(w.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    w.index = idx
    return w


def clip10(w):
    return w[(w.index.year >= 2016) & (w.index.year <= 2025)]


def h1_night():
    """H1副確認: GER=月曜最終バー→火曜初バー / US=月曜20:00UTC→火曜13:00UTC。"""
    res = {}
    hashes = {}
    for sym, name in H1_SYMS.items():
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
             f"?interval=1h&period1={H1_P1}&period2={H1_P2}")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read()
        hashes[name] = hashlib.sha256(raw).hexdigest()[:16]
        d = json.loads(raw)
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        byday = {}
        for i, t in enumerate(ts):
            o = q["open"][i]
            if o is None:
                continue
            u_ = dt.datetime.fromtimestamp(t, dt.timezone.utc)
            byday.setdefault(u_.date(), []).append((u_, float(o)))
        days = sorted(byday)
        rets = {}
        for di, day in enumerate(days[:-1]):
            if day.weekday() != 0:
                continue
            bars = byday[day]
            if name == "GER40":
                p0 = bars[-1][1]                       # 月曜最終バー
                nxt = byday[days[di + 1]]
                p1 = nxt[0][1]                          # 翌営業日初バー
            else:
                ent = [b for b in bars if b[0].hour == 20]
                nxt = [b for b in byday[days[di + 1]] if b[0].hour == 13]
                if not ent or not nxt:
                    continue
                p0 = ent[0][1]; p1 = nxt[0][1]
            rets[day] = p1 / p0 - 1.0 - COST
        res[name] = pd.Series(rets)
    s = pd.DataFrame(res).mean(axis=1, skipna=True).dropna()
    return dict(net_pct=round(float(s.sum() * 100), 2), weeks=int(len(s)),
                worst_week=round(float(s.min() * 100), 2)), hashes


def main():
    # 主判定
    H24 = clip10(weekly("o2o"))
    HNO = clip10(weekly("c2o"))
    HDC = clip10(weekly("o2c"))
    m24, mno, mdc = metrics(H24), metrics(HNO), metrics(HDC)
    print("日足10年:")
    print("  H24(現行):", m24)
    print("  HNO(夜間):", mno)
    print("  HDC(参考・日中):", mdc)
    ref26 = {t: round(float(weekly(k)[weekly(k).index.year == 2026].sum() * 100), 2)
             for t, k in (("H24", "o2o"), ("HNO", "c2o"))}
    print("  2026H1参考:", ref26)

    # 月曜特異性プラセボ(c2oを全曜日で)
    plc = {}
    for wd, nmj in ((0, "月"), (1, "火"), (2, "水"), (3, "木"), (4, "金")):
        plc[nmj] = metrics(clip10(weekly("c2o", weekday=wd)))
    rank = sorted(plc, key=lambda k: plc[k]["score"], reverse=True)
    print("プラセボ(c2o曜日別score):", {k: plc[k]["score"] for k in rank}, "→ 月曜の順位:", rank.index("月") + 1)

    # 年次JK: 除外年別に score(HNO)≥score(H24) か
    jk = {}
    ok_jk = 0
    for y in range(2016, 2026):
        a = metrics(H24[H24.index.year != y]); b = metrics(HNO[HNO.index.year != y])
        win = bool(b["score"] >= a["score"])
        ok_jk += int(win)
        jk[y] = dict(H24=a["score"], HNO=b["score"], HNO_wins=win)
    print(f"年次JK: HNO勝ち {ok_jk}/10")

    # IS/OOS 70:30
    cut = int(len(H24) * 0.7)
    isoos = dict(IS=dict(H24=metrics(H24.iloc[:cut]), HNO=metrics(HNO.iloc[:cut])),
                 OOS=dict(H24=metrics(H24.iloc[cut:]), HNO=metrics(HNO.iloc[cut:])))
    print("IS/OOS: IS", {k: v["score"] for k, v in isoos["IS"].items()},
          " OOS", {k: v["score"] for k, v in isoos["OOS"].items()})

    # コスト2倍
    c2 = dict(H24=metrics(clip10(weekly("o2o", cost_mult=2.0))),
              HNO=metrics(clip10(weekly("c2o", cost_mult=2.0))))
    print("コスト2倍 score:", {k: v["score"] for k, v in c2.items()})

    # H1副確認
    h1, h1sha = h1_night()
    print("H1副確認(HNO・約2年):", h1)

    # 決定規則(docs/119 §4・6条件全て必須)
    checks = dict(
        score_110pct=bool(mno["score"] >= 1.1 * m24["score"]),
        net_80pct=bool(mno["net_pct"] >= 0.8 * m24["net_pct"]),
        monday_top1=bool(rank.index("月") == 0),
        jk_8of10=bool(ok_jk >= 8),
        cost2x_rank=bool(c2["HNO"]["score"] >= c2["H24"]["score"]),
        h1_positive=bool(h1["net_pct"] > 0))
    decision = "HNO採用" if all(checks.values()) else \
        f"H24維持(不合格: {[k for k, v in checks.items() if not v]})"
    print("決定:", decision)

    out = dict(prereg="docs/119", window_daily="2016-01..2025-12(固定窓CSV=docs/114と同一)",
               daily=dict(H24=m24, HNO=mno, HDC_ref=mdc), ref_2026H1=ref26,
               placebo_weekday_c2o={k: plc[k] for k in plc}, monday_rank=rank.index("月") + 1,
               jackknife=jk, jk_wins=ok_jk, isoos=isoos, cost2x=c2,
               h1_secondary=dict(window="2024-07-09..2026-07-07", sha256=h1sha, HNO=h1),
               checks=checks, decision=decision)
    path = os.path.join(HERE, "results", "edge22_emon_night_10y.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
