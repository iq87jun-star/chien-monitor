# -*- coding: utf-8 -*-
"""
recency_track.py — docs/174(事前登録)の実行: 直近特化トラック。
「直近W(6/12)ヶ月のネットリターン上位k本を逆ボラ加重で翌月保有」を
2017-01〜2026-07でウォークフォワードし、docs/111機械(中央3ヶ月校正・日次ブロックMC)で
失格率を現行(季節R4+G3・同一窓)と同一土俵比較する。

⚠ docs/174コミット後に実行。規則・グリッド・判定基準は同docから変更しない。
データ: Yahoo日足 2015-01-01〜2026-07-31(取得日2026-07-30・7月は月途中)。
出力: results/recency_track.json → docs/175
"""
import os, sys, json, csv, time, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

P1, P2 = 1420070400, 1785542399   # 2015-01-01 .. 2026-07-31 UTC
from seasonal_optimize_loyo import SYMBOLS  # 20銘柄(凍結)

W0 = pd.Timestamp("2017-01-01")   # WF適用窓(docs/174 §3)
W1 = pd.Timestamp("2026-07-31")
SEED, N_FINAL = 7, 20000
YEN7 = ["EURJPY", "GBPJPY", "USDJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
IDX6 = ["NAS100", "US500", "GER40", "JP225", "UK100", "FR40"]
HOLD7 = ["US500", "NAS100", "GER40", "JP225", "UK100", "FR40", "XAUUSD"]
VARIANTS = ([("mean", w, k) for w in (6, 12) for k in (2, 3, 5)]
            + [("sharpe", 12, 3), ("sharpe", 6, 3)])          # docs/174 §2(凍結8変種)


def fetch_all():
    os.makedirs(DATA, exist_ok=True)
    for name, sym in SYMBOLS.items():
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/"
             f"{urllib.parse.quote(sym)}?interval=1d&period1={P1}&period2={P2}")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                         .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
        p = os.path.join(DATA, f"{name}_d.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
        print(f"  {name}: {len(rows)} bars ..{rows[-1][0][:10]}"); time.sleep(0.6)


def sha256s():
    return {n: hashlib.sha256(open(os.path.join(DATA, f"{n}_d.csv"), "rb").read()).hexdigest()[:16]
            for n in SYMBOLS if os.path.exists(os.path.join(DATA, f"{n}_d.csv"))}


def build_units():
    """docs/174 §1の22ユニット(既存実装を逐語再利用・窓のみ延長)"""
    import portfolio_daily_compare as pdc
    pdc.W0, pdc.W1 = pd.Timestamp("2015-06-01"), W1   # 選択窓(2016)の分まで遡って保持
    units = {}
    for s in YEN7:
        units[f"Mon_{s}"] = pdc.mon_daily([s])
    for s in IDX6:
        units[f"Mon_{s}"] = pdc.mon_daily([s], 3e-4)
    for s in HOLD7:
        u = pdc.cc_daily([s]).copy()
        firsts = pd.Series(u.index, index=u.index).groupby(pd.PeriodIndex(u.index, freq="M")).min()
        u.loc[u.index.isin(firsts.values)] -= 5e-4     # 月初5bp(docs/174 §1)
        units[f"Hold_{s}"] = u
    units["v4"] = pdc.v4_daily()
    units["E5"] = pdc.e5_daily()
    return pdc, units


def walk_forward(df, score_kind, W, k):
    """月初に直近W暦月で採点→上位k(スコア>0)を逆ボラ加重で当月保有。→(日次系列, 選択ログ)"""
    mk = pd.PeriodIndex(df.index, freq="M")
    months = [m for m in sorted(set(mk)) if pd.Timestamp("2017-01") <= m.to_timestamp() <= W1]
    out, log = [], {}
    for m in months:
        w0, w1 = m - W, m - 1
        win = df[(mk >= w0) & (mk <= w1)]
        score = win.sum(skipna=True)
        vol = win.std(skipna=True)
        obs = win.notna().sum()
        if score_kind == "sharpe":
            score = score / (vol * np.sqrt(obs)).replace(0, np.nan)
        elig = score[(score > 0) & (vol > 0) & (obs >= 4 * W // 2)]  # 最低限の観測数
        pick = elig.sort_values(ascending=False).head(k)
        if len(pick) == 0:
            log[str(m)] = {}
            continue
        iv = 1.0 / vol[pick.index]
        wts = iv / iv.sum()
        cur = df.loc[mk == m, pick.index].fillna(0.0)
        out.append((cur * wts).sum(axis=1))
        log[str(m)] = {u: round(float(x), 4) for u, x in wts.items()}
    s = pd.concat(out).sort_index() if out else pd.Series(dtype=float)
    # ノーポジ月も暦日を残す(校正の月数を揃える): 全月インデックスへ0埋めはせず月配列側で処理
    return s, log


def mstats(s):
    m = pd.Series({k: float((1 + s[pd.PeriodIndex(s.index, freq='M') == k]).prod() - 1)
                   for k in pd.PeriodIndex(s.index, freq="M").unique()}).sort_index()
    sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    yearly = {str(y): round(float((1 + m[m.index.year == y]).prod() - 1) * 100, 1)
              for y in sorted(set(m.index.year))}
    return dict(mean_month=round(float(m.mean() * 100), 2), sharpe=round(sh, 2),
                worst_month=round(float(m.min() * 100), 2),
                worst_day=round(float(s.min() * 100), 2), yearly=yearly)


def calib_and_mc(series, g3=None, label=""):
    """docs/111機械を逐語再利用して中央3ヶ月校正+2万パスMC"""
    from median3_calibrate_compare import (month_arrays, month_stats_at, simulate,
                                           calibrate_median3)
    arrs = month_arrays(series)
    g3a = None
    if g3 is not None:
        g3s = g3.reindex(series.index).fillna(0.0)
        mk = pd.PeriodIndex(series.index, freq="M")
        g3a = [np.asarray(g3s[mk == m].values, float) for m in mk.unique()]
    mult, _ = calibrate_median3(arrs, g3a, np.random.default_rng(SEED))
    if mult is None:
        print(f"  {label}: 中央3ヶ月に到達不可(≤4x)")
        return dict(note="中央3ヶ月に到達不可(≤4x)")
    st = simulate(month_stats_at(arrs, mult, g3a), N_FINAL, np.random.default_rng(SEED))
    s = series * mult
    if g3 is not None:
        s = s.add(g3, fill_value=0.0)
    rec = dict(mult=mult, **st, **mstats(s))
    print(f"  {label}: mult={mult} pass={st['pass_pct']}% "
          f"fail={st['fail_pct_optimistic']}/{st['fail_pct_raw']}% med={st['median_months']}m")
    return rec


def p2_pass_pct(series, mult):
    """P2(+5%・同フロア)の通過率: TARGETだけ差し替えた同一機械(docs/175のEV用)"""
    import median3_calibrate_compare as m3
    from median3_calibrate_compare import month_arrays, month_stats_at, simulate
    old = m3.TARGET
    try:
        m3.TARGET = 0.05
        st = simulate(month_stats_at(month_arrays(series), mult), N_FINAL,
                      np.random.default_rng(SEED))
    finally:
        m3.TARGET = old
    return st


def current_pick(df, score_kind, W, k):
    """2026-08月初時点の採用ユニット(=EA焼き込み用)と、その重み固定の直近12ヶ月IS成績"""
    mk = pd.PeriodIndex(df.index, freq="M")
    m = pd.Period("2026-08", freq="M")
    win = df[(mk >= m - W) & (mk <= m - 1)]
    score = win.sum(skipna=True); vol = win.std(skipna=True); obs = win.notna().sum()
    if score_kind == "sharpe":
        score = score / (vol * np.sqrt(obs)).replace(0, np.nan)
    elig = score[(score > 0) & (vol > 0) & (obs >= 4 * W // 2)]
    pick = elig.sort_values(ascending=False).head(k)
    iv = 1.0 / vol[pick.index]; wts = iv / iv.sum()
    is12 = df[(mk >= pd.Period("2025-08")) & (mk <= pd.Period("2026-07"))][pick.index]
    is_series = (is12.fillna(0.0) * wts).sum(axis=1)
    return ({u: round(float(x), 4) for u, x in wts.items()},
            {u: round(float(score[u]) * 100, 2) for u in pick.index}, mstats(is_series))


def main():
    if not os.path.exists(os.path.join(DATA, "US500_d.csv")) or "--fetch" in sys.argv:
        print("[0/4] データ取得(2015-01-01..2026-07-31)")
        fetch_all()

    print("[1/4] 22ユニット構築")
    pdc, units = build_units()
    df = pd.DataFrame(units)
    df = df[df.index <= W1]
    print("  units:", len(units), "rows:", len(df), df.index.min().date(), "..", df.index.max().date())

    print("[2/4] ウォークフォワード8変種(2017-01..2026-07)+校正MC")
    out, series_map = {}, {}
    for kind, W, k in VARIANTS:
        name = f"{kind}_W{W}_k{k}"
        s, log = walk_forward(df, kind, W, k)
        flat = sum(1 for v in log.values() if not v)
        rec = calib_and_mc(s, label=name)
        rec["flat_months"] = flat
        rec["turnover_note"] = f"選択ログは results/recency_track_picks.json"
        out[name] = rec; series_map[name] = (s, log)

    print("[3/4] 対照: 季節R4+G3(同一窓2017-01..2026-07)")
    from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS
    from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                         composite_daily, YEN, V7X, EMON, EMONX)
    import portfolio_daily_compare as _pdc
    _pdc.FOMC = _pdc.FOMC + ["2026-06-17", "2026-07-29"]   # EA入力(2026年分)と整合
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    base = composite_daily(sleeves, R4)
    base = base[base.index >= W0]
    g3 = g3_daily(); g3 = g3[g3.index >= W0]
    out["対照_季節R4+G3"] = calib_and_mc(base, g3, label="季節R4+G3(同窓)")

    print("[4/4] 判定(docs/174 §4)+現時点ピック+P2/EV")
    scored = [(v["fail_pct_optimistic"], v["fail_pct_raw"], -v.get("sharpe", 0), k)
              for k, v in out.items() if "mult" in v and not k.startswith("対照")]
    adopt = sorted(scored)[0][3]
    kind, W, k = [(a, b, c) for (a, b, c) in VARIANTS if f"{a}_W{b}_k{c}" == adopt][0]
    wts, scores, is12 = current_pick(df, kind, W, k)
    s_ad, log_ad = series_map[adopt]
    p2 = p2_pass_pct(s_ad, out[adopt]["mult"])
    p2b = p2_pass_pct(base, out["対照_季節R4+G3"]["mult"])  # 対照はG3抜き系列でP2近似
    print(f"  採用変種: {adopt} / 現時点ピック: {wts}")

    res = dict(meta=dict(prereg="docs/174", window=f"WF {W0.date()}..{W1.date()}",
                         data="Yahoo日足 2015-01-01..2026-07-31(2026-07は月途中=30日まで)",
                         method="docs/111逐語(日次ブロックMC・FN P1+8%・シード7・2万パス)",
                         inputs=sha256s(),
                         caveat="Yahoo日足近似。WF行が実力・IS行は選択バイアス込みの見かけ。"),
               variants=out, adopted=adopt,
               current_pick=dict(weights=wts, trailing_score_pct=scores,
                                 is_last12m=is12,
                                 note="重みの有効期限3ヶ月(docs/174 §4)・毎月再計算が本則"),
               p2_estimate={adopt: p2, "対照(G3抜き近似)": p2b})
    with open(os.path.join(HERE, "results", "recency_track.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    picks = {name: lg for name, (s, lg) in series_map.items()}
    with open(os.path.join(HERE, "results", "recency_track_picks.json"), "w") as f:
        json.dump(picks, f, ensure_ascii=False, indent=1)
    print("保存: results/recency_track.json / recency_track_picks.json")


if __name__ == "__main__":
    main()
