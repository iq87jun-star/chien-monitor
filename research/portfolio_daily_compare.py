# -*- coding: utf-8 -*-
"""
portfolio_daily_compare.py — 現行EA(M3) vs 提案(R3a/R4) の【日次解像度】比較。
ユーザー依頼(2026-07): 「リスク倍率を調整して比較 + 現状のものにFOMC(G3)も入れて」。

方法(docs/87の倍率規律をコード化):
  1) 各スリーブの日次リターンを再構築(v4はトレード単位の日次時価評価・v7系は月曜o2o・
     E5/S-Julは日次c2c×月次ポジション・G3はFOMC前日の日足プロキシ)
  2) 各構成の倍率を【ガード逆算】で校正: max{m : 最悪単日×m≥−4% かつ 最悪月中DD×m≥−8%}×0.8
  3) 校正済み倍率で 月次成績・7+8月P1通過確率(ブートストラップ) を横並び比較
⚠ G3日足プロキシは実測(H1)の約2割しか捉えない(docs/86 H14b)=G3寄与は控えめ側の表示。
⚠ Yahoo日足近似。相対比較が主眼。出力: results/portfolio_daily_compare.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from parallel_vs_existing_compare import load_daily as _load_daily, pip_size


def load_daily(name):
    """tz-naive index に統一(比較・searchsorted の型事故防止)"""
    df = _load_daily(name).copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx
    return df
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS

YEN = ["EURJPY", "GBPJPY", "USDJPY"]; V7X = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
EMON = ["NAS100", "US500", "GER40"]; EMONX = ["JP225", "UK100", "FR40"]
E5B = ["XAUUSD", "US500", "NAS100", "GER40"]; SJUL = ["US500", "NAS100"]
W0, W1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2026-06-30")
FOMC = [
 "2016-01-27","2016-03-16","2016-04-27","2016-06-15","2016-07-27","2016-09-21","2016-11-02","2016-12-14",
 "2017-02-01","2017-03-15","2017-05-03","2017-06-14","2017-07-26","2017-09-20","2017-11-01","2017-12-13",
 "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
 "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
 "2020-01-29","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
 "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
 "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
 "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
 "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
 "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
 "2026-01-28","2026-03-18","2026-04-29"]  # docs/81 §5(+2026)

# 現行M3(=YEARROUND_05テーブル, EA WY配列と同一)
M3 = {1: {"EMon": 1.0}, 2: {"v4": 1.0},
      3: {"EMon": .33, "EMonX": .28, "v4": .19, "E5": .20}, 4: {"EMonX": 1.0},
      5: {"v4": .46, "v7x": .31, "v7": .23},
      6: {"v4": .38, "E5": .36, "EMon": .15, "EMonX": .12},
      7: {"SJul": .76, "E5": .24}, 8: {"v4": .46, "E5": .41, "EMonX": .13},
      9: {"v4": 1.0}, 10: {"EMonX": 1.0}, 11: {"EMon": 1.0},
      12: {"E5": .42, "EMon": .36, "v4": .23}}


def clip(s):
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s = pd.Series(np.asarray(s.values, dtype=float), index=idx)
    return s[(s.index >= W0) & (s.index <= W1)]


def mon_daily(names, idx_cost=None):
    parts = []
    for nm in names:
        df = load_daily(nm)
        cost = (idx_cost if idx_cost is not None else 2 * pip_size(nm) / df["open"])
        parts.append((df[df["weekday"] == 0]["o2o"] - cost).rename(nm))
    return clip(pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna())


def cc_daily(names):
    parts = [load_daily(nm)["close"].pct_change().rename(nm) for nm in names]
    return clip(pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna())


def e5_daily():
    closes = {}
    for nm in E5B:
        df = load_daily(nm); s = df["close"]; s.index = pd.to_datetime(df.index)
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    vol = ret.rolling(12).std().shift(1)
    w = (1 / vol).div((1 / vol).sum(axis=1), axis=0)
    pw = (pos * w)
    pw.index = pw.index.to_period("M")
    daily = {}
    dparts = {nm: load_daily(nm)["close"].pct_change() for nm in E5B}
    for nm in E5B:
        s = dparts[nm].dropna()
        mkey = pd.PeriodIndex(pd.to_datetime(s.index), freq="M")
        coef = pw[nm].reindex(mkey).values
        daily[nm] = pd.Series(s.values * coef, index=s.index)
    out = pd.DataFrame(daily).sum(axis=1, skipna=True)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    return clip(out.dropna())


def rsi_w(c, n=14):
    d = np.diff(c, prepend=c[0]); up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1 / n
    for i in range(1, len(c)):
        au[i] = a * up[i] + (1 - a) * au[i - 1]; ad[i] = a * dn[i] + (1 - a) * ad[i - 1]
    return 100 - 100 / (1 + au / np.where(ad == 0, 1e-12, ad))


def atr_d(hh, ll, cc, n=14):
    pc = np.roll(cc, 1); pc[0] = cc[0]
    tr = np.maximum(hh - ll, np.maximum(np.abs(hh - pc), np.abs(ll - pc)))
    o = np.empty_like(tr); o[0] = tr[0]; a = 1 / n
    for i in range(1, len(tr)):
        o[i] = a * tr[i] + (1 - a) * o[i - 1]
    return o


def v4_daily():
    """ea_benchmark v4_series と同一トレードを日次時価評価で展開"""
    V4P = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
    acc = {}
    for p in V4P:
        df = load_daily(p)
        o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c); rsi = rsi_w(c); atr = atr_d(hh, ll, c); bb = 20
        cost = 2 * pip_size(p); i = bb + 2
        while i < n - 1:
            win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1)
            z = (c[i] - mean) / sd if sd > 0 else 0
            down = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
                else: break
            retd = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0
            buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(retd < -.005)
            sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(retd > .005)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0:
                i += 1; continue
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0 or entry <= 0:
                i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
            while j < n and held < 8:
                if sig > 0:
                    if ll[j] <= sl: ex = sl; break
                    if hh[j] >= tp: ex = tp; break
                else:
                    if hh[j] >= sl: ex = sl; break
                    if ll[j] <= tp: ex = tp; break
                j += 1; held += 1
            jx = min(j, n - 1)
            if ex is None: ex = c[jx]
            prev = entry
            for t in range(i + 1, jx + 1):
                px = ex if t == jx else c[t]
                r = sig * (px - prev) / entry
                if t == i + 1: r -= cost / entry
                acc[idx[t]] = acc.get(idx[t], 0.0) + r
                prev = px
            i = max(i + 1, j)
    return clip(pd.Series(acc).sort_index())


def g3_daily(event_risk=0.01):
    df = load_daily("US500"); c = df["close"].values
    atr = atr_d(df["high"].values, df["low"].values, c)
    idx = pd.to_datetime(df.index); out = {}
    dates = pd.DatetimeIndex(idx)
    for d in FOMC:
        T = pd.Timestamp(d)
        pos = dates.searchsorted(T)
        if pos < 2 or pos >= len(dates):
            continue
        i1 = pos - 1; i2 = pos - 2                    # T-1日(声明前日)のc2c
        af = atr[i2] / c[i2]
        noty = min(event_risk / max(af, 1e-4), 1.5)
        out[idx[i1]] = noty * (c[i1] / c[i2] - 1.0) - 1e-4
    return clip(pd.Series(out).sort_index())


def composite_daily(sleeves, wmap):
    idx = sorted(set().union(*[set(s.index) for s in sleeves.values()]))
    idx = [t for t in idx if W0 <= t <= W1]
    vals = []
    for t in idx:
        w = wmap[t.month]
        vals.append(sum(w.get(k, 0.0) * float(sleeves[k].get(t, 0.0)) for k in sleeves))
    return pd.Series(vals, index=pd.DatetimeIndex(idx))


def worst_stats(daily):
    wd = float(daily.min())
    mk = pd.PeriodIndex(daily.index, freq="M")
    wdd = 0.0
    for m in mk.unique():
        s = daily[mk == m]
        eq = (1 + s).cumprod()
        dd = float(((eq - eq.cummax()) / eq.cummax()).min())
        wdd = min(wdd, dd)
    return wd, wdd


def calibrate(base, g3=None, day_cap=0.04, floor_cap=0.08):
    best = 0.05
    for m in np.arange(0.05, 5.01, 0.05):
        s = base * m
        if g3 is not None:
            s = s.add(g3, fill_value=0.0)
        wd, wdd = worst_stats(s)
        if wd >= -day_cap and wdd >= -floor_cap:
            best = m
        else:
            break
    return round(0.8 * best, 2)


def monthly_stats(daily):
    mk = pd.PeriodIndex(daily.index, freq="M")
    mret = pd.Series({m: float((1 + daily[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()
    eq = (1 + mret).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = mret.mean() * 12; vol = mret.std() * np.sqrt(12)
    cagr = (eq.iloc[-1] ** (12 / len(mret)) - 1) * 100
    jul = mret[[m.month == 7 for m in mret.index]].values
    aug = mret[[m.month == 8 for m in mret.index]].values
    rng = np.random.default_rng(7)
    cum = (1 + rng.choice(jul, 20000)) * (1 + rng.choice(aug, 20000)) - 1
    return dict(mean_month=round(float(mret.mean() * 100), 2), cagr=round(float(cagr), 1),
                sharpe=round(float(mu / vol) if vol > 0 else 0, 2), maxDD=round(dd, 1),
                worst_month=round(float(mret.min() * 100), 2),
                worst_day=round(float(daily.min() * 100), 2),
                p_pass_JulAug=round(float((cum >= 0.08).mean() * 100), 1),
                months=int(len(mret)))


def main():
    print("[1/3] 日次スリーブ構築")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(SJUL), v4=v4_daily())
    g3 = g3_daily()
    print("  ", {k: len(v) for k, v in sleeves.items()}, "G3 events:", len(g3))

    print("[2/3] 月次重みテーブル(R3a/R4は全期間訓練=配備時と同じ立場)")
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    RMAP = {}
    for rule in ("R3a", "R4"):
        RMAP[rule] = {m: weights_for(rule, mu.loc[m], sd.loc[m]) for m in range(1, 13)}

    print("[3/3] 校正と比較")
    out = {}
    variants = [("M3(現行)", M3, False), ("M3+G3", M3, True),
                ("R3a", RMAP["R3a"], False), ("R3a+G3", RMAP["R3a"], True),
                ("R4", RMAP["R4"], False), ("R4+G3", RMAP["R4"], True)]
    for name, wmap, useG3 in variants:
        base = composite_daily(sleeves, wmap)
        rec = calibrate(base, g3 if useG3 else None)
        s = base * rec
        if useG3:
            s = s.add(g3, fill_value=0.0)
        st = monthly_stats(s)
        wd, wdd = worst_stats(s)
        st["mult"] = rec; st["worst_intramonth_DD"] = round(wdd * 100, 1)
        out[name] = st
        print(f"  {name:10s} mult={rec:.2f} {st}")

    # パネルB: チャレンジ速攻(現行M3=2.0x基準の等テール換算)。等テール= 校正倍率比でスケール
    ref = 2.0 / out["M3(現行)"]["mult"]          # M3の校正倍率→2.0x への倍率比
    outB = {}
    for name, wmap, useG3 in variants:
        base = composite_daily(sleeves, wmap)
        mult = round(out[name.replace("+G3", "").replace("(現行)", "") if False else name]["mult"] * ref, 2)
        s = base * mult
        if useG3:
            s = s.add(g3, fill_value=0.0)
        st = monthly_stats(s)
        wd, wdd = worst_stats(s)
        st["mult"] = mult; st["worst_intramonth_DD"] = round(wdd * 100, 1)
        outB[name] = st
        print(f"  [速攻] {name:10s} mult={mult:.2f} {st}")

    res = dict(method="docs/87 倍率規律: min(日次-4%,フロア-8%)逆算×0.8 / G3=日足プロキシ(実測の~2割・控えめ)",
               window=f"{W0.date()}..{W1.date()}", variants=out,
               panelB_challenge_equal_tail=dict(note="現行M3=2.0x基準・校正倍率比で等テール換算。"
                                                     "worst_dayが-5%超の行はFN日次規約を踏み抜き得る(=失格テール)",
                                                variants=outB))
    path = os.path.join(HERE, "results", "portfolio_daily_compare.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
