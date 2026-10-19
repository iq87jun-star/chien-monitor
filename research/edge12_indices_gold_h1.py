# -*- coding: utf-8 -*-
"""edge12 — Dukascopy H1 株価指数・金 セッション構造エッジ検定（事前登録 docs/81）。

確認的仮説（N_conf=3 → Bonferroni α=0.0167）:
  G1_EQ_OVERNIGHT  指数オーバーナイト: 現物クローズ直前バー終値→翌オープン前バー終値 LONG
                   (US500/NAS100=ET 15時台→翌8時台, GER40=ベルリン 17時台→翌8時台)
  G2_GOLD_OVERNIGHT 金オーバーナイト: ET 16時台終値(≒COMEXクローズ)→翌7時台終値 LONG
  G3_FOMC_DRIFT    FOMC声明前24hドリフト: 前日ET13時台終値→当日13時台終値 LONG (定例82回)
探索的スキャン（参考のみ・採否に不使用）: 現地時間hour×{L,S}の無条件ドリフト。

ゲート(docs/81 §3): G_perm<=0.0167 / G_jk<=0.10 / G_oos両+ / G_indep(|ρv7|<=0.4かつ|ρE-Mon|<=0.5) /
  G_plac(ドリフト保存プラセボ) / G_cost(取引コスト×0.5-×4で+) ＋ スワップ感応(0/1.5/2.5/4bps/晩)
  ＋ 事後診断(対B&H・ON/OFF条件付き平均)。B&H劣後はp値に関わらず実質REJECT(docs/80 F2の教訓)。

統計関数は edge6/edge11 と同一。ローダは colab_v7_confidence.py / edge10 準拠。
実データ未配置時は EDGE12_SELFTEST=1 で合成H1によりエンジン健全性のみ自己テスト
（埋め込みオーバーナイト・ドリフトを検出し、ドリフト保存プラセボとの差が出ることを確認。
 ⚠合成は連続ドリフト＝ランダム窓プラセボも有意になり得る。実エッジ判定には実データのみ）。
"""
import os, json, hashlib, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# ---------- 設定 ----------
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"
START, END = "2016-01-01", "2026-06-01"
SEED = 13
BONF = 0.05 / 3

EQ   = ["US500", "NAS100", "GER40"]
TZ   = {"US500": "America/New_York", "NAS100": "America/New_York",
        "GER40": "Europe/Berlin",    "XAUUSD": "America/New_York"}
# (entry現地hour, exit現地hour) — docs/81 §1 で固定
SESS = {"US500": (15, 8), "NAS100": (15, 8), "GER40": (17, 8), "XAUUSD": (16, 7)}
COST_RT_BPS = {"US500": 1.0, "NAS100": 1.5, "GER40": 1.5, "XAUUSD": 2.5}
FIN_BPS_NIGHT = 2.5            # 基準金融コスト/晩(ロング)。感応 0/1.5/2.5/4.0
YEN = ["EURJPY", "GBPJPY", "USDJPY"]

FOMC = [  # docs/81 §5 固定(定例82回・声明日)
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
 "2026-01-28","2026-03-18","2026-04-29"]

# ---------- ローダ（edge10準拠 + dukascopy-node のms timestamp対応） ----------
def _resolve(name):
    b = H1_DIR.format(base=DRIVE_BASE)
    for x in [f"{b}/{name}_h1.csv", f"{b}/{name}.csv",
              f"{LOCAL_FALLBACK}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}.csv"]:
        if os.path.exists(x): return x
    return None

def _synth_h1(name, seed):
    """自己テスト用合成H1。乱歩 + 埋め込み(オーバーナイト時間帯に正ドリフト)。"""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-04", "2026-05-29 23:00", freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    loc = idx.tz_convert(TZ.get(name, "America/New_York"))
    e_h, x_h = SESS.get(name, (15, 8))
    overnight = (loc.hour >= e_h + 1) | (loc.hour <= x_h)   # 埋め込み対象時間帯
    base = 2000.0 if name != "XAUUSD" else 1500.0
    step = rng.normal(0, base*8e-4, len(idx))               # ~8bps/h ボラ
    step[overnight] += base*1.0e-4                          # ★オーバーナイトに+1bp/hドリフト
    close = base + np.cumsum(step)
    o = close - step
    h = np.maximum(o, close) + np.abs(rng.normal(0, base*3e-4, len(idx)))
    l = np.minimum(o, close) - np.abs(rng.normal(0, base*3e-4, len(idx)))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": close}, index=idx)

CACHE = {}
def load_h1(name):
    if name in CACHE: return CACHE[name]
    path = _resolve(name)
    if path is None:
        if os.environ.get("EDGE12_SELFTEST") == "1":
            CACHE[name] = _synth_h1(name, SEED + hash(name) % 1000); return CACHE[name]
        raise FileNotFoundError(
            f"{name} H1 CSV 未検出。{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv を配置"
            "（docs/81 §6: npx dukascopy-node で取得）")
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    raw = df[tcol]
    if pd.api.types.is_numeric_dtype(raw) and raw.abs().max() > 1e11:   # dukascopy-node ms
        df["t"] = pd.to_datetime(raw, unit="ms", utc=True)
    else:
        df["t"] = pd.to_datetime(raw, utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pick(*n):
        for x in n:
            if x in df.columns: return x
        return None
    cols = {k: pick(k, f"bid{k}", k[0]) for k in ["open","high","low","close"]}
    out = pd.DataFrame({k: df[v].astype(float) for k, v in cols.items() if v}, index=df.index)
    out = out[(out.index >= pd.Timestamp(START, tz="UTC")) & (out.index < pd.Timestamp(END, tz="UTC"))]
    CACHE[name] = out.dropna()
    return CACHE[name]

def sha_of(name):
    p = _resolve(name)
    if p is None: return "selftest"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()[:16]

# ---------- 統計ハーネス（edge6/edge11と同一） ----------
def perm_p(r, n=3000, seed=SEED):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())
def perm_p_robust(s, n=3000, seed=SEED):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    return perm_p(s.groupby(s.index.to_period("M")).sum().values, n=n, seed=seed)
def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0.0, win_pct=0.0, maxDD_pct=0.0, n=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round(float(eq.iloc[-1]-1)*100, 1), win_pct=round(float((x > 0).mean())*100, 0),
                maxDD_pct=round(float(dd), 1), n=int(len(x)))
def jackknife(s):
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    jk = {int(y): round(perm_p_robust(s[s.index.year != y]), 3) for y in yrs}
    return jk, round(max(jk.values()), 3)
def mP(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)
def _series_from(legs):
    if not legs: return pd.Series(dtype=float)
    s = pd.Series([v for _, v in legs], index=pd.DatetimeIndex([t for t, _ in legs]))
    return s.groupby(s.index).mean().sort_index()

# ---------- 基準系列（独立性ゲート用） ----------
def v7_monthly():
    """円月曜LONG(H1, 月曜00UTC終値→火曜00UTC終値近似)月次。FX H1未配置ならNone。"""
    legs = []
    for p in YEN:
        try: df = load_h1(p) if (_resolve(p) or os.environ.get("EDGE12_SELFTEST") != "1") else None
        except FileNotFoundError: df = None
        if df is None or len(df) == 0: continue
        c = df["close"]; mon = c[(c.index.dayofweek == 0) & (c.index.hour == 0)]
        for t in mon.index:
            seg = c[(c.index > t) & (c.index <= t + pd.Timedelta(hours=24))]
            if len(seg) == 0: continue
            legs.append((t.tz_localize(None).normalize(), float(seg.iloc[-1]/mon[t] - 1) - 2e-4))
    return mP(_series_from(legs)) if legs else None

def emon_monthly():
    """E-Mon近似(指数 月曜LONG: 金曜最終バー終値→月曜最終バー終値)月次。同一H1から再現。"""
    legs = []
    for a in EQ:
        c = load_h1(a)["close"]; days = c.groupby(c.index.tz_convert(TZ[a]).date).last()
        di = pd.DatetimeIndex(days.index)
        for i in range(1, len(days)):
            if di[i].dayofweek == 0:
                legs.append((di[i], float(days.iloc[i]/days.iloc[i-1] - 1) - COST_RT_BPS[a]/1e4))
    return mP(_series_from(legs))

# ---------- セッション・エンジン ----------
def _local_frame(name):
    df = load_h1(name)
    loc = df.index.tz_convert(TZ[name])
    return pd.DataFrame({"close": df["close"].values, "date": loc.date, "hour": loc.hour},
                        index=df.index)

def session_shots(name, entry_h, exit_h, cost_mult=1.0, fin_bps=FIN_BPS_NIGHT,
                  placebo=False, seed=1):
    """entry_h時台バー終値→翌営業日exit_h時台バー終値 LONG。
    placebo=同保有バー数・ランダム開始(ドリフト保存, docs/80 §5)。"""
    rng = np.random.default_rng(seed)
    f = _local_frame(name); c = f["close"].values
    dates = sorted(set(f["date"]))
    pos_by_date = {}
    for i, (t, row) in enumerate(zip(f.index, f.itertuples())):
        pos_by_date.setdefault(row.date, {})[row.hour] = i
    cost = COST_RT_BPS[name]/1e4 * cost_mult
    legs = []
    for k in range(len(dates)-1):
        d0 = pos_by_date.get(dates[k], {}); i0 = d0.get(entry_h)
        i1 = pos_by_date.get(dates[k+1], {}).get(exit_h)
        if i0 is None or i1 is None or i1 <= i0: continue
        if placebo:
            span = i1 - i0
            j0 = int(rng.integers(0, max(1, len(c)-span-1))); j1 = j0 + span
            i0, i1 = j0, j1
        nights = max(1, (pd.Timestamp(dates[k+1]) - pd.Timestamp(dates[k])).days)
        r = c[i1]/c[i0] - 1.0 - cost - nights*fin_bps/1e4
        legs.append((f.index[i0].tz_localize(None).normalize(), r))
    return _series_from(legs)

def g1_eq_overnight(cost_mult=1.0, fin_bps=FIN_BPS_NIGHT, placebo=False, seed=1):
    parts = [session_shots(a, *SESS[a], cost_mult=cost_mult, fin_bps=fin_bps,
                           placebo=placebo, seed=seed+i) for i, a in enumerate(EQ)]
    allidx = sorted(set().union(*[set(p.index) for p in parts if len(p)]))
    return pd.concat(parts, axis=1).reindex(allidx).mean(axis=1).dropna()

def g2_gold_overnight(cost_mult=1.0, fin_bps=FIN_BPS_NIGHT, placebo=False, seed=2):
    return session_shots("XAUUSD", *SESS["XAUUSD"], cost_mult=cost_mult, fin_bps=fin_bps,
                         placebo=placebo, seed=seed)

def g3_fomc_drift(cost_mult=1.0, fin_bps=FIN_BPS_NIGHT, placebo=False, seed=3):
    """前日13時台ET終値→当日13時台ET終値 LONG。placebo=同窓・ランダム非FOMC火水(年同数)。"""
    rng = np.random.default_rng(seed)
    f = _local_frame("US500")
    bars13 = f[f["hour"] == 13]
    by_date = {d: i for d, i in zip(bars13["date"], range(len(bars13)))}
    c13 = bars13["close"].values; idx13 = bars13.index
    fomc = set(pd.Timestamp(d).date() for d in FOMC)
    targets = sorted(d for d in by_date if d in fomc)
    if placebo:
        cands = [d for d in by_date if d not in fomc
                 and pd.Timestamp(d).dayofweek in (1, 2)]
        per_yr = {}
        for d in targets: per_yr[d.year] = per_yr.get(d.year, 0) + 1
        picks = []
        for y, k in per_yr.items():
            pool = [d for d in cands if d.year == y]
            if len(pool) >= k: picks += list(rng.choice(pool, size=k, replace=False))
        targets = sorted(picks)
    cost = COST_RT_BPS["US500"]/1e4 * cost_mult
    legs = []
    for d in targets:
        j = by_date[d]
        if j == 0: continue
        nights = max(1, (pd.Timestamp(d) - pd.Timestamp(bars13["date"].iloc[j-1])).days)
        r = c13[j]/c13[j-1] - 1.0 - cost - nights*fin_bps/1e4
        legs.append((idx13[j-1].tz_localize(None).normalize(), r))
    return _series_from(legs)

CAND = {"G1_EQ_OVERNIGHT": g1_eq_overnight, "G2_GOLD_OVERNIGHT": g2_gold_overnight,
        "G3_FOMC_DRIFT": g3_fomc_drift}
MIN_N = {"G3_FOMC_DRIFT": 50}

# ---------- 事後診断（採用判定外・docs/80 標準） ----------
def diagnostics(name):
    out = {}
    insts = EQ if name == "G1_EQ_OVERNIGHT" else ["XAUUSD"] if name == "G2_GOLD_OVERNIGHT" else ["US500"]
    for a in insts:
        f = _local_frame(name=a)
        days = f.groupby("date")["close"].last()
        bh = stats(pd.Series(days.values, index=pd.DatetimeIndex(days.index)).pct_change().dropna())
        e_h, x_h = SESS[a]
        on = session_shots(a, e_h, x_h, cost_mult=0.0, fin_bps=0.0)   # 摩擦ゼロの素リターン
        dd = pd.Series(days.values, index=pd.DatetimeIndex(days.index)).pct_change().dropna()
        on_m = mP(on); dd_m = mP(dd)
        j = pd.concat([on_m.rename("on"), dd_m.rename("all")], axis=1).dropna()
        intraday_mean = float((j["all"] - j["on"]).mean()) / 21 * 1e4
        out[a] = dict(bh_net=bh["net_pct"], bh_maxDD=bh["maxDD_pct"],
                      overnight_mean_bps=round(float(on.mean())*1e4, 2),
                      intraday_mean_bps_approx=round(intraday_mean, 2))
    return out

# ---------- 探索的スキャン（参考のみ） ----------
def hour_scan(name):
    f = _local_frame(name); c = f["close"]
    r = c.pct_change().shift(-1)
    rows = {}
    for h in range(24):
        m = r[f["hour"] == h].dropna()
        if len(m) < 200: continue
        rows[h] = dict(mean_bps=round(float(m.mean())*1e4, 2), n=int(len(m)))
    return rows

# ---------- 実行 ----------
def run():
    selftest = os.environ.get("EDGE12_SELFTEST") == "1"
    print(("⚠ SELFTEST(合成データ・実エッジ判定不可)\n" if selftest else "") +
          f"事前登録N=3 Bonferroniα={round(BONF,4)} / 金融コスト基準{FIN_BPS_NIGHT}bps/晩 / span {START}〜{END}")
    ym = v7_monthly(); em = emon_monthly()
    print(f"基準系列: v7={'None(FX H1未配置→ρv7省略)' if ym is None else f'{len(ym)}ヶ月'} / E-Mon={len(em)}ヶ月")
    out = {"meta": dict(n=3, bonferroni_alpha=round(BONF, 4), span=[START, END], selftest=selftest,
                        cost_rt_bps=COST_RT_BPS, fin_bps_night=FIN_BPS_NIGHT,
                        inputs={a: sha_of(a) for a in EQ + ["XAUUSD"]}),
           "candidates": {}, "hour_scan_exploratory": {}}
    for name, fn in CAND.items():
        s = fn()
        if len(s) < MIN_N.get(name, 200):
            out["candidates"][name] = dict(note="insufficient", n=int(len(s)))
            print(f"\n{name}: データ不足 n={len(s)}"); continue
        st = stats(s); p = round(perm_p_robust(s), 4)
        jk = jackknife(s); jkmax = jk[1] if jk else None
        h = s.index[len(s)//2]; isr, oos = s[s.index < h], s[s.index >= h]
        cm = mP(s)
        rho_v7 = None if ym is None else round(float(pd.concat([cm, ym], axis=1).dropna().corr().iloc[0, 1]), 2)
        rho_em = round(float(pd.concat([cm, em], axis=1).dropna().corr().iloc[0, 1]), 2)
        plc = fn(placebo=True); plc_p = round(perm_p_robust(plc), 3); plc_net = stats(plc)["net_pct"]
        cost = {f"x{m}": stats(fn(cost_mult=m))["net_pct"] for m in (0.5, 1, 2, 4)}
        fin  = {f"{b}bps": stats(fn(fin_bps=b))["net_pct"] for b in (0.0, 1.5, 2.5, 4.0)}
        diag = diagnostics(name)
        g_perm = p <= BONF; g_jk = (jkmax is not None and jkmax <= 0.10)
        g_oos = (isr.sum() > 0 and oos.sum() > 0)
        g_indep = ((rho_v7 is None or abs(rho_v7) <= 0.4) and abs(rho_em) <= 0.5)
        g_plac = (plc_p > 0.05 and st["net_pct"] > plc_net)
        g_cost = all(v > 0 for v in cost.values())
        bh_worst = max(d["bh_net"] for d in diag.values())
        beats_bh = st["net_pct"] > 0 and not (st["net_pct"] < bh_worst and st["maxDD_pct"] <= max(d["bh_maxDD"] for d in diag.values()))
        passed = sum([g_perm, g_jk, g_oos, g_indep, g_plac, g_cost])
        grade = "ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac and beats_bh) else \
                ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")
        if grade == "LEAD" and fin["0.0bps"] > 0 >= fin[f"{FIN_BPS_NIGHT}bps"]:
            grade = "LEAD(swap-free限定)"
        out["candidates"][name] = dict(**st, perm_p=p, jackknife_max_p=jkmax,
            IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"],
            corr_to_v7=rho_v7, corr_to_emon=rho_em, placebo_net=plc_net, placebo_p=plc_p,
            cost_mult=cost, financing=fin, diagnostics=diag,
            gates=dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost),
            beats_bh=beats_bh, gates_passed=f"{passed}/6", grade=grade)
        print(f"\n### {name}  [{grade}] {passed}/6" +
              ("" if st["maxDD_pct"] >= -10 else f" ⚠DD{st['maxDD_pct']}%≫-10%=素サイズ不可"))
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p={p}(Bonf{round(BONF,4)}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | ρv7={rho_v7} ρE-Mon={rho_em}({g_indep}) | placebo{plc_net}%/p{plc_p}({g_plac})")
        print(f"   cost{cost}({g_cost}) | swap{fin} | 対B&H={beats_bh} 診断{diag}")
    for a in EQ + ["XAUUSD"]:
        out["hour_scan_exploratory"][a] = hour_scan(a)
    adopts = [n for n, r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads  = [n for n, r in out["candidates"].items() if str(r.get("grade", "")).startswith("LEAD")]
    print("\n>>> ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 全滅 → 指数・金H1でも新エッジ無し=探索の完全終了(docs/80 §4)。")
    out["adopted"] = adopts; out["leads"] = leads
    drive_ok = os.path.exists("/content/drive/MyDrive")
    path = (H1_DIR.format(base=DRIVE_BASE) + "/edge12_indices_gold_h1.json") if drive_ok \
           else "research/results/edge12_indices_gold_h1.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存:", path)
    return out

if __name__ == "__main__":
    run()
