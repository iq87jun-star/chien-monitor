# -*- coding: utf-8 -*-
"""
edge23_cot_positioning.py — CFTC COT JPYポジショニング【事前登録 docs/127】。
H23a: 投機筋net/OIの52週z極値の逆張り(±2.0固定・20営業日保有・USDJPY)
H23b: net/OIの4週変化符号のフロー持続(週次リバランス・USDJPY)
H23c: v7円月曜レッグの「投機筋JPYネットショート週」条件付け(ON/OFF差+ON比率保存プラセボ)
ゲート: docs/127 §3(G1経済性/G2 perm≤0.01/G3年次JK/G4 IS-OOS/G5プラセボ/G6コスト2倍/
G7耐久分類/G8独立性)。感応グリッドは記録のみ・昇格不可。シード=23/123固定。
ルックアヘッド対策: COT火曜集計・金曜公表 → as-of+6暦日以降の最初の取引日から有効。
"""
import os, io, json, hashlib, zipfile, urllib.request, importlib.util, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

LOCAL = "./research/data"
os.makedirs(LOCAL, exist_ok=True)
END = "2026-06-01"          # edge13と同一の凍結終端
MAIN0, MAIN1 = "2016-01-01", "2026-01-01"   # 主判定 2016-2025
PRE0 = "1999-01-01"                          # 耐久分類 1999-2015
ALPHA = 0.01
RT_PIPS = 2.0               # USDJPY往復コスト(pips)。G6は2倍=4.0
JPY_CODE = "097741"

# ---- 価格: edge13の *_lh_d.csv を自前生成(yfinance不要・Yahoo v8直)して逐語再利用 ----
_YH = {"USDJPY": "JPY=X", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
       "US500": "%5EGSPC", "NAS100": "%5EIXIC", "GER40": "%5EGDAXI", "XAUUSD": "GC=F"}

def prefetch(name):
    path = f"{LOCAL}/{name}_lh_d.csv"
    if os.path.exists(path): return
    p1 = 473385600  # 1985-01-01
    p2 = int(pd.Timestamp(END, tz="UTC").timestamp())
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{_YH[name]}?interval=1d&period1={p1}&period2={p2}"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    # FX日足はSun23:00UTC刻印=bar openのため +2h floor で取引日へ正規化(docs/14と同じ流儀)
    idx = (pd.to_datetime(ts, unit="s", utc=True) + pd.Timedelta(hours=2)).tz_localize(None).floor("D")
    s = pd.Series(q["close"], index=idx, dtype=float).dropna()
    s = s.groupby(s.index).last()
    s.rename("close").to_csv(path, index_label="date")

for _n in _YH: prefetch(_n)

spec = importlib.util.spec_from_file_location("e13", "research/edge13_longhistory_confirm.py")
e13 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e13)

def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f: h.update(f.read())
    return h.hexdigest()[:16]

# ---- COT取得(legacy futures-only・1999-2026・JPY=097741) ----
def cot_jpy():
    path = f"{LOCAL}/cot_jpy_legacy.csv"
    if not os.path.exists(path):
        rows = []
        for y in range(1999, 2027):
            u = f"https://www.cftc.gov/files/dea/history/deacot{y}.zip"
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                raw = urllib.request.urlopen(req, timeout=60).read()
            except Exception as e:
                print(f"  COT {y}: 取得失敗 {type(e).__name__}"); continue
            zf = zipfile.ZipFile(io.BytesIO(raw))
            df = pd.read_csv(zf.open(zf.namelist()[0]), dtype=str, low_memory=False)
            df.columns = [c.strip().lstrip("﻿") for c in df.columns]
            code_c = next(c for c in df.columns if c.startswith("CFTC Contract Market Code") and "Quotes" not in c)
            name_c = next(c for c in df.columns if c.startswith("Market and Exchange Names"))
            j = df[(df[code_c].str.strip() == JPY_CODE) |
                   (df[name_c].str.strip().str.upper().str.startswith("JAPANESE YEN"))].copy()
            if len(j) == 0:
                print(f"  COT {y}: JPY行なし"); continue
            d6 = next(c for c in j.columns if "As of Date in Form YYMMDD" in c)
            j["asof"] = pd.to_datetime(j[d6].str.strip(), format="%y%m%d")
            for src, dst in [("Open Interest (All)", "oi"),
                             ("Noncommercial Positions-Long (All)", "ncl"),
                             ("Noncommercial Positions-Short (All)", "ncs")]:
                col = next(c for c in j.columns if c.strip() == src)
                j[dst] = pd.to_numeric(j[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
            rows.append(j[["asof", "oi", "ncl", "ncs"]])
            print(f"  COT {y}: {len(j)}行")
        allj = pd.concat(rows).dropna().sort_values("asof").drop_duplicates("asof")
        allj.to_csv(path, index=False)
    df = pd.read_csv(path, parse_dates=["asof"]).sort_values("asof").drop_duplicates("asof")
    df["net_spec"] = (df["ncl"] - df["ncs"]) / df["oi"]
    df = df.set_index("asof")
    df["z52"] = (df["net_spec"] - df["net_spec"].rolling(52, min_periods=40).mean()) / \
                df["net_spec"].rolling(52, min_periods=40).std()
    df["d4w"] = df["net_spec"] - df["net_spec"].shift(4)
    df["d1w"] = df["net_spec"] - df["net_spec"].shift(1)
    df["d13w"] = df["net_spec"] - df["net_spec"].shift(13)
    return df

# ---- 共通 ----
px = e13.daily("USDJPY")
pidx = px.index

def eff_day(asof):
    """as-of(火曜)+6暦日以降の最初の取引日=翌週月曜(ルックアヘッド遮断)。"""
    i = pidx.searchsorted(asof + pd.Timedelta(days=6))
    return pidx[i] if i < len(pidx) else None

def stats_win(s, a, b):
    return e13.stats(s[(s.index >= a) & (s.index < b)])

def in_win(s, a, b):
    return s[(s.index >= a) & (s.index < b)]

# ---- H23a: 極値逆張り(state machine・エントリー日で窓判定・リターンは決済日に計上) ----
def run_h23a(cot, z_th=2.0, hold=20, rt=RT_PIPS):
    trades = []   # (entry_date, exit_date, ret, side)
    busy_until = -1
    for asof, row in cot.iterrows():
        z = row["z52"]
        if not np.isfinite(z) or abs(z) < z_th: continue
        d = eff_day(asof)
        if d is None: continue
        i = pidx.searchsorted(d)
        if i <= busy_until: continue          # 保有中の新シグナルは無視
        j = i + hold
        if j >= len(pidx): continue
        e, x = float(px.iloc[i]), float(px.iloc[j])
        side = -1.0 if z <= -z_th else +1.0   # z<=-th: 投機筋極端JPYショート→JPY LONG=USDJPY SHORT
        ret = side * (x / e - 1.0) - rt * 0.01 / e
        trades.append((pidx[i], pidx[j], ret, side))
        busy_until = j
    ent = pd.Series([r for _, _, r, _ in trades], index=[t0 for t0, _, _, _ in trades]).sort_index()
    return ent, trades

# ---- H23b: フロー持続(週次) ----
def run_h23b(cot, dcol="d4w", rt=RT_PIPS):
    recs = []
    prev_side, prev_day = 0.0, None
    for asof, row in cot.iterrows():
        v = row[dcol]
        if not np.isfinite(v): continue
        d = eff_day(asof)
        if d is None: continue
        recs.append((d, +0.0 if v == 0 else (-1.0 if v > 0 else +1.0)))
        # d4w>0=投機筋JPY買い越し→JPY LONG=USDJPY SHORT(side=-1)
    rets = {}
    for k in range(len(recs) - 1):
        d0, side = recs[k]
        d1 = recs[k + 1][0]
        if side == 0 or d1 <= d0: continue
        e, x = float(px.asof(d0)), float(px.asof(d1))
        flip = (side != (recs[k - 1][1] if k > 0 else 0.0))
        cost = (rt * 0.01 / e) if flip else 0.0
        rets[d1] = side * (x / e - 1.0) - cost
    return pd.Series(rets).sort_index(), recs

def placebo_h23b(recs, a, b, rt=RT_PIPS, n=400, seed=123):
    rng = np.random.default_rng(seed)
    win = [(d, s) for d, s in recs if a <= str(d.date()) < b]
    days = [d for d, _ in win]; sides = np.array([s for _, s in win])
    nets = []
    for _ in range(n):
        perm = rng.permutation(sides)
        tot, prev = 0.0, 0.0
        for k in range(len(days) - 1):
            side = perm[k]
            if side == 0: prev = side; continue
            e, x = float(px.asof(days[k])), float(px.asof(days[k + 1]))
            cost = (rt * 0.01 / e) if side != prev else 0.0
            tot += side * (x / e - 1.0) - cost
            prev = side
        nets.append(tot * 100)
    return float(np.percentile(nets, 95))

# ---- 採点 ----
def gates(s, sens_fn=None, placebo_p95=None, rho_v7=None, rho_e5=None, cost2_net=None):
    main = in_win(s, MAIN0, MAIN1)
    st = e13.stats(main)
    p = round(e13.perm_p_robust(main), 4)
    jk = e13.jackknife_max(main)
    is_, oos = in_win(s, "2016-01-01", "2021-01-01"), in_win(s, "2021-01-01", MAIN1)
    pre = in_win(s, PRE0, "2016-01-01")
    ref26 = in_win(s, "2026-01-01", "2026-07-01")
    g = dict(
        G1_econ=bool(st["net_pct"] > 0 and st["net_pct"] / 10.0 >= 1.0),
        G2_perm=bool(p <= ALPHA),
        G3_jk=bool(jk is not None and jk <= 0.10),
        G4_isoos=bool(e13.stats(is_)["net_pct"] > 0 and e13.stats(oos)["net_pct"] > 0),
        G5_placebo=bool(placebo_p95 is not None and st["net_pct"] > placebo_p95),
        G6_cost2=bool(cost2_net is not None and cost2_net > 0),
        G8_indep=bool((rho_v7 is None or abs(rho_v7) <= 0.4) and (rho_e5 is None or abs(rho_e5) <= 0.4)),
    )
    adopt = all(g.values())
    lead = st["net_pct"] > 0 and p <= 0.05
    verdict = "ADOPT候補" if adopt else ("LEAD" if lead else "REJECT")
    return dict(main=dict(**st, perm_p=p, jk_max=jk,
                          is_net=e13.stats(is_)["net_pct"], oos_net=e13.stats(oos)["net_pct"]),
                pre_1999_2015=dict(net_pct=e13.stats(pre)["net_pct"], n=e13.stats(pre)["n"],
                                   durability="長期構造" if e13.stats(pre)["net_pct"] > 0 else "現行レジーム"),
                ref_2026H1_net=e13.stats(ref26)["net_pct"],
                placebo_p95=placebo_p95, cost2_net=cost2_net,
                rho_v7=rho_v7, rho_e5=rho_e5, gates=g, verdict=verdict)

def rho_monthly(s, ref):
    a = in_win(s, MAIN0, MAIN1); b = in_win(ref, MAIN0, MAIN1)
    am = a.groupby(a.index.to_period("M")).sum(); bm = b.groupby(b.index.to_period("M")).sum()
    j = pd.concat([am.rename("a"), bm.rename("b")], axis=1).dropna()
    return round(float(j["a"].corr(j["b"])), 2) if len(j) > 24 else None

def run():
    cot = cot_jpy()
    v7 = e13.v7_proxy()
    e5 = e13.e5()
    out = {"meta": dict(prereg="docs/127", alpha=ALPHA, rt_pips=RT_PIPS, seed_perm=13, seed_placebo=123,
                        cot_span=[str(cot.index[0].date()), str(cot.index[-1].date())], cot_n=int(len(cot)),
                        inputs=dict(cot=sha_file(f"{LOCAL}/cot_jpy_legacy.csv"),
                                    **{k: e13.sha(k) for k in _YH}))}

    # ---- H23a 主要(z2.0 / 20d) ----
    s_a, tr_a = run_h23a(cot)
    # placebo: ON数・L/S構成保存のランダム配置
    rng = np.random.default_rng(123)
    elig = sorted({d for d in (eff_day(t) for t in cot.index) if d is not None
                   and MAIN0 <= str(d.date()) < MAIN1 and pidx.searchsorted(d) + 20 < len(pidx)})
    main_tr = [t for t in tr_a if MAIN0 <= str(t[0].date()) < MAIN1]
    sides_real = [sd for _, _, _, sd in main_tr]
    plc_nets = []
    if len(main_tr) > 0 and len(elig) >= len(main_tr):
        for _ in range(400):
            days = rng.choice(len(elig), size=len(main_tr), replace=False)
            sides = rng.permutation(sides_real)
            tot = 0.0
            for di, sd in zip(days, sides):
                i = pidx.searchsorted(elig[int(di)]); j = i + 20
                e_, x_ = float(px.iloc[i]), float(px.iloc[j])
                tot += sd * (x_ / e_ - 1.0) - RT_PIPS * 0.01 / e_
            plc_nets.append(tot * 100)
    plc95_a = float(np.percentile(plc_nets, 95)) if plc_nets else None
    s_a2, _ = run_h23a(cot, rt=RT_PIPS * 2)
    out["H23a"] = gates(s_a, placebo_p95=round(plc95_a, 1) if plc95_a is not None else None,
                        rho_v7=rho_monthly(s_a, v7), rho_e5=rho_monthly(s_a, e5),
                        cost2_net=stats_win(s_a2, MAIN0, MAIN1)["net_pct"])
    out["H23a"]["n_trades_main"] = len(main_tr)
    out["H23a"]["sens(記録のみ・昇格不可)"] = {
        f"z{th}_h{hd}": stats_win(run_h23a(cot, z_th=th, hold=hd)[0], MAIN0, MAIN1)["net_pct"]
        for th in (1.5, 2.5) for hd in (5, 10)}

    # ---- H23b 主要(Δ4w / 1w) ----
    s_b, recs_b = run_h23b(cot)
    plc95_b = placebo_h23b(recs_b, MAIN0, MAIN1)
    s_b2, _ = run_h23b(cot, rt=RT_PIPS * 2)
    out["H23b"] = gates(s_b, placebo_p95=round(plc95_b, 1),
                        rho_v7=rho_monthly(s_b, v7), rho_e5=rho_monthly(s_b, e5),
                        cost2_net=stats_win(s_b2, MAIN0, MAIN1)["net_pct"])
    out["H23b"]["sens(記録のみ・昇格不可)"] = {
        d: stats_win(run_h23b(cot, dcol=d)[0], MAIN0, MAIN1)["net_pct"] for d in ("d1w", "d13w")}

    # ---- H23c v7条件付け ----
    v7m = in_win(v7, MAIN0, MAIN1)
    eff = pd.Series(cot["net_spec"].values,
                    index=[eff_day(t) for t in cot.index]).dropna().sort_index()
    eff = eff[~eff.index.duplicated(keep="last")]
    lab = pd.Series(np.nan, index=v7m.index)
    for m in v7m.index:
        prior = eff[eff.index <= m]
        if len(prior): lab[m] = prior.iloc[-1]
    on = v7m[lab < 0]; off = v7m[lab >= 0]
    diff = float(on.mean() - off.mean())
    rng2 = np.random.default_rng(13)
    labs = (lab < 0).values
    diffs = []
    vals = v7m.values
    for _ in range(3000):
        p_ = rng2.permutation(labs)
        diffs.append(vals[p_].mean() - vals[~p_].mean())
    p_c = float((np.array(diffs) >= diff).mean())
    rng3 = np.random.default_rng(123)
    on_net_real = float(on.sum()) * 100
    plc_on = []
    for _ in range(400):
        m_ = np.zeros(len(v7m), bool); m_[rng3.choice(len(v7m), size=int(labs.sum()), replace=False)] = True
        plc_on.append(vals[m_].sum() * 100)
    plc95_c = float(np.percentile(plc_on, 95))
    tot_net = float(v7m.sum()) * 100
    c1 = p_c <= ALPHA; c2 = on_net_real > plc95_c; c3 = on_net_real >= 0.8 * tot_net
    out["H23c"] = dict(on_weeks=int(labs.sum()), off_weeks=int((~labs).sum()),
                       on_mean_bps=round(float(on.mean()) * 1e4, 2), off_mean_bps=round(float(off.mean()) * 1e4, 2),
                       diff_perm_p=round(p_c, 4), on_net_pct=round(on_net_real, 1),
                       uncond_net_pct=round(tot_net, 1), placebo_p95_pct=round(plc95_c, 1),
                       gates=dict(c1_perm=bool(c1), c2_placebo=bool(c2), c3_retain80=bool(c3)),
                       verdict="v7フィルタ提案(要ユーザー承認)" if (c1 and c2 and c3) else "現行v7無条件を維持")

    os.makedirs("research/results", exist_ok=True)
    with open("research/results/edge23_cot_positioning.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)

    for h in ("H23a", "H23b"):
        r = out[h]
        print(f"### {h} → {r['verdict']}")
        print(f"  main net {r['main']['net_pct']}% p={r['main']['perm_p']} JK={r['main']['jk_max']} "
              f"IS/OOS {r['main']['is_net']}/{r['main']['oos_net']} n={r['main']['n']}")
        print(f"  placebo95 {r['placebo_p95']} cost2 {r['cost2_net']} ρv7 {r['rho_v7']} ρE5 {r['rho_e5']} "
              f"pre {r['pre_1999_2015']['net_pct']}%({r['pre_1999_2015']['durability']}) gates {r['gates']}")
    print(f"### H23c → {out['H23c']['verdict']}")
    print(f"  ON {out['H23c']['on_weeks']}w mean {out['H23c']['on_mean_bps']}bps / OFF {out['H23c']['off_weeks']}w "
          f"mean {out['H23c']['off_mean_bps']}bps p={out['H23c']['diff_perm_p']} "
          f"ONnet {out['H23c']['on_net_pct']}% vs 無条件 {out['H23c']['uncond_net_pct']}% plc95 {out['H23c']['placebo_p95_pct']}%")
    print("保存: research/results/edge23_cot_positioning.json")
    return out

if __name__ == "__main__":
    run()
