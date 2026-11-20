# -*- coding: utf-8 -*-
"""docs/252 第 5 段: H1 の条件付きセル(新規探索)。F1 アジアレンジ・ブレイク 152 / F2 週明けギャップ 76 / F3 日中継続 114 / F4 クロスアセット先行 36 = 378 セル + F1'(終値判定・152)+ F4'(13-20/16-20・36)= 566 セル。
F1 は始値判定が退化(06 時バーの高安を含むため発生 2〜3 回)、F4 は 21 時バーの欠損で月数 17 に減ったため、初回実行後に F1'/F4' を追加(結果を見て条件を変えたのではなく仕様の退化の修正。旧 F1/F4 も累積に数える)。
19 銘柄(Dukascopy H1)。始値→出口時刻の始値。コスト: FX 往復 3pip / 指数 IDX_COST / XAUUSD 5bps。方向を先に決めてからコスト(docs/249)+ 自己検証。
窓: 前窓 2016-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾。判定: 二項 p(IS の +月数)< 0.05/(3,934+378)=1.16e-5、IS 月数 ≥ 24、OOS 平均 > 0、前窓 +月率 ≥ 50%。research/ で実行。"""
import os, sys, glob, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
ALPHA = 0.05 / (3934 + 378 + 152 + 36)   # F1'/F4' の追加分も事前に加算
SYMS = sorted(os.path.basename(f).replace("_hour.csv.gz", "") for f in glob.glob("data_dukascopy/*_hour.csv.gz"))
def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def cost_frac(sym, px):
    c = base.IDX_COST.get(sym)
    if c is not None: return np.full_like(px, c, dtype=float)
    if sym == "XAUUSD": return np.full_like(px, 5e-4, dtype=float)
    return 3 * base.pip_size(sym) / px
def make(sym, t_in, px_in, dir_, o, hold_h):
    """t_in: 建て時刻, px_in: 建値, dir_: +1/-1 の方向配列, hold_h: 保有時間。方向を先に決めてからコストを引く。"""
    t_out = t_in + pd.Timedelta(hours=hold_h); px_out = o.reindex(t_out).values; ok = ~np.isnan(px_out) & (dir_ != 0)
    r = dir_[ok] * (px_out[ok] / px_in[ok] - 1.0) - cost_frac(sym, px_in[ok])
    return pd.Series(r, index=t_in[ok])
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan, p=1.0, trades=0)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(m)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean=round(float(x.mean()) * 1e4, 1), p=p, trades=len(x))
rows = []
def add(fam, sym, spec, r):
    sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2026-12-31"))
    passed = si["p"] < ALPHA and si["n"] >= 24 and so["n"] > 0 and so["mean"] > 0 and sp["n"] > 0 and sp["rate"] >= 0.5
    rows.append(dict(family=fam, symbol=sym, spec=spec, is_plus=si["plus"], is_n=si["n"], is_rate=si["rate"], is_mean_bps=si["mean"], is_trades=si["trades"], p=si["p"],
                     oos_plus=so["plus"], oos_n=so["n"], oos_mean_bps=so["mean"], pre_n=sp["n"], pre_rate=sp["rate"], passed=passed))
data = {s: load(s) for s in SYMS}
us = data["US500"]; us_o = us["open"]
for sym in SYMS:
    df = data[sym]; o = df["open"]; h = df["high"]; l = df["low"]; c = df["close"]
    # 自己検証: 同一建てで LONG+SHORT = −2×コスト
    t0 = o.index[(o.index.hour == 8) & (o.index.dayofweek == 1)][:200]; p0 = o.reindex(t0).values
    z = (make(sym, t0, p0, np.ones(len(t0)), o, 4) + make(sym, t0, p0, -np.ones(len(t0)), o, 4)).dropna()
    assert len(z) == 0 or float(z.max()) <= 1e-12, f"[COST SIGN] {sym}"
    day = df.index.floor("D")
    # F1 アジアレンジ(00〜06 UTC の 7 バー)ブレイク
    asia = df[df.index.hour <= 6]; rng = asia.groupby(asia.index.floor("D")).agg(hi=("high", "max"), lo=("low", "min"), n=("high", "size")); rng = rng[rng.n >= 5]
    for trig in (7, 8):
        tt = o.index[(o.index.hour == trig) & (o.index.dayofweek <= 4)]; px = o.reindex(tt).values; d = tt.floor("D")
        hi = rng["hi"].reindex(d).values; lo = rng["lo"].reindex(d).values
        brk = np.where(px > hi, 1, np.where(px < lo, -1, 0)); brk = np.where(np.isnan(hi), 0, brk)
        for hold in (4, 8):
            for lab, sgn in (("追随", 1), ("逆行", -1)):
                add("F1 アジアレンジ", sym, f"trig{trig:02d} hold{hold}h {lab}", make(sym, tt, px, sgn * brk, o, hold))
    # F1': 07 / 08 時バーの終値がレンジ外 → 次バー(08 / 09 時)始値で建てる
    for trig in (7, 8):
        tb = c.index[(c.index.hour == trig) & (c.index.dayofweek <= 4)]; cl = c.reindex(tb).values; d = tb.floor("D")
        hi = rng["hi"].reindex(d).values; lo = rng["lo"].reindex(d).values
        brk = np.where(cl > hi, 1, np.where(cl < lo, -1, 0)); brk = np.where(np.isnan(hi), 0, brk)
        tt = tb + pd.Timedelta(hours=1); px = o.reindex(tt).values; ok = ~np.isnan(px)
        for hold in (4, 8):
            for lab, sgn in (("追随", 1), ("逆行", -1)):
                add("F1' アジアレンジ(終値判定)", sym, f"bar{trig:02d}close→{trig+1:02d} hold{hold}h {lab}", make(sym, tt[ok], px[ok], (sgn * brk)[ok], o, hold))
    # F2 週明けギャップ: 月曜最初のバー始値 vs 金曜最終バー終値
    fri_last = c[c.index.dayofweek == 4].groupby(c[c.index.dayofweek == 4].index.floor("D")).last()
    mon_first_t = o[o.index.dayofweek == 0].groupby(o[o.index.dayofweek == 0].index.floor("D")).apply(lambda q: q.index[0])
    tt = pd.DatetimeIndex(mon_first_t.values); px = o.reindex(tt).values
    prev_fri = pd.DatetimeIndex([t.floor("D") - pd.Timedelta(days=3) for t in tt]); fc = fri_last.reindex(prev_fri).values
    gap = np.where(np.isnan(fc), 0, np.sign(px - fc))
    for hold in (12, 24):
        for lab, sgn in (("追随", 1), ("逆行", -1)):
            add("F2 週明けギャップ", sym, f"hold{hold}h {lab}", make(sym, tt, px, sgn * gap, o, hold))
    # F3 日中継続: s から 4h の方向 → s+4 で建て 8h
    for s0 in (0, 7, 13):
        ts = o.index[(o.index.hour == s0) & (o.index.dayofweek <= 4)]; p_s = o.reindex(ts).values; t4 = ts + pd.Timedelta(hours=4); p4 = o.reindex(t4).values
        sig = np.where(np.isnan(p4), 0, np.sign(p4 - p_s)); ok = ~np.isnan(p4)
        for lab, sgn in (("追随", 1), ("逆行", -1)):
            add("F3 日中継続", sym, f"start{s0:02d} +4h→8h {lab}", make(sym, t4[ok], p4[ok], (sgn * sig)[ok], o, 8))
    # F4 クロスアセット先行(US500 → 東京時間)
    if sym in ("AUDJPY", "CADJPY", "CHFJPY", "EURJPY", "GBPJPY", "NZDJPY", "USDJPY", "AUDUSD", "NZDUSD"):
        tt = o.index[(o.index.hour == 0) & (o.index.dayofweek <= 4)]; px = o.reindex(tt).values
        for lab_l, (h_a, h_b) in (("US13-21", (13, 21)), ("US17-21", (17, 21)), ("US13-20", (13, 20)), ("US16-20", (16, 20))):
            prev = tt - pd.Timedelta(days=1); prev = pd.DatetimeIndex([t - pd.Timedelta(days=2) if t.dayofweek == 6 else t for t in prev])   # 月曜は金曜を参照
            a = us_o.reindex(prev + pd.Timedelta(hours=h_a)).values; b = us_o.reindex(prev + pd.Timedelta(hours=h_b)).values
            sig = np.where(np.isnan(a) | np.isnan(b), 0, np.sign(b - a))
            for lab, sgn in (("追随", 1), ("逆行", -1)):
                add("F4 クロスアセット" + ("'" if h_b == 20 else ""), sym, f"{lab_l} → 00-08 {lab}", make(sym, tt, px, sgn * sig, o, 8))
R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q11_stage5_conditional.csv", index=False); pd.set_option("display.width", 250)
print(f"cells={len(R)} alpha={ALPHA:.2e} passed={int(R.passed.sum())}  p<0.05: {int((R.p<0.05).sum())}(偶然期待 {len(R)*0.05:.0f})")
print(R.head(15).to_string(index=False)); print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
print("\n-- 族別: セル数 / p<0.05 / 良い側 IS +月率 中央値 --")
g = R.copy(); g["best"] = g.groupby(["family", "symbol", g.spec.str.replace("追随", "").str.replace("逆行", "")]).is_rate.transform("max")
print(pd.DataFrame({"n": R.groupby("family").size(), "p005": R[R.p < 0.05].groupby("family").size(), "med_best_rate": g[g.is_rate == g.best].groupby("family").is_rate.median().round(3)}).fillna(0).to_string())
