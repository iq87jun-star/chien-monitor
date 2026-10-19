# -*- coding: utf-8 -*-
"""edge18 — v7横展開(新4 JPYクロス)の Dukascopy H1 正式検証【事前登録 docs/95】。

凍結ルール: 月曜04/06/08/10UTC LONG→24h・往復2pip・週次リスク均等割り
(colab_validate_all_v7standard.py の yen_weekly を銘柄だけ替えて逐語流用)。
9ゲート(docs/40同一): G3 α=0.01(保守固定) / G4 月曜のみ有意(火-金プラセボ) / G5 JK<=0.10 /
G6 IS-OOS / G7 WF>=4/5 / G8 2×コスト / G9 p95maxDD>=-10%。
判定: 全コア通過=ADOPT(v7同格) / G3orG5のみ未達(G4,G6,G7,G8通過)=STRONG-LEAD / 他=LEAD。
実データ未配置時は EDGE18_SELFTEST=1 で合成H1(月曜ドリフト埋込み)のエンジン自己テストのみ。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"
NEW4   = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
YEN3   = ["EURJPY", "GBPJPY", "USDJPY"]   # 参考ρ用(存在すれば)
HOURS  = [4, 6, 8, 10]
COST_PIP = 2.0
ALPHA  = 0.01
N_PATHS = 4000; SEED = 13

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(name):
    b = H1_DIR.format(base=DRIVE_BASE)
    for x in [f"{b}/{name}_h1.csv", f"{b}/{name}.csv",
              f"{LOCAL_FALLBACK}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}.csv"]:
        if os.path.exists(x): return x
    return None

def _synth_h1(pair, seed):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-04", "2026-05-29 23:00", freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    pip = pip_size(pair); base = 90.0
    step = rng.normal(0, 6*pip, len(idx))
    step[(idx.dayofweek == 0) & (idx.hour >= 4) & (idx.hour <= 14)] += 1.0*pip  # ★月曜日中ドリフト埋込み
    close = base + np.cumsum(step)
    return pd.Series(close, index=idx)

CACHE = {}
def H1C(p):
    if p in CACHE: return CACHE[p]
    path = _resolve(p)
    if path is None:
        if os.environ.get("EDGE18_SELFTEST") == "1":
            CACHE[p] = _synth_h1(p, SEED + hash(p) % 997); return CACHE[p]
        return None
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    raw = df[tcol]
    if pd.api.types.is_numeric_dtype(raw) and raw.abs().max() > 1e11:
        df["t"] = pd.to_datetime(raw, unit="ms", utc=True)
    else:
        df["t"] = pd.to_datetime(raw, utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc = next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    CACHE[p] = pd.Series(df[cc].astype(float).values, index=df.index).dropna()
    return CACHE[p]

# ---------- 戦略系列(colab_validate_all_v7standard.yen_weekly 逐語・銘柄パラメタ化) ----------
def basket_weekly(pairs, hold=24, weekday=0, hours=HOURS, cost_pip=COST_PIP, budget=1.0):
    cols = []
    for p in pairs:
        s = H1C(p)
        if s is None: continue
        cv = s.values; idx = s.index; ps = pip_size(p)
        for h in hours:
            a = np.where((idx.dayofweek == weekday) & (idx.hour == h))[0]; a = a[a+hold < len(cv)]
            r = pd.Series((cv[a+hold]-cv[a])/cv[a] - cost_pip*ps/cv[a], index=idx[a].to_period("W"))
            cols.append(r[~r.index.duplicated()])
    if not cols: return pd.Series(dtype=float)
    M = pd.concat(cols, axis=1).sort_index()
    out = {}
    for wk, row in M.iterrows():
        rs = row.dropna()
        if len(rs): out[wk] = float((budget/len(rs)*rs).sum())
    s = pd.Series(out).sort_index(); s.index = s.index.to_timestamp(); return s

# ---------- 統計(同・逐語) ----------
def perm_p(s, n=4000, seed=13):
    r = pd.Series(s).dropna().values
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())
def stat(s, ann=52):
    s = pd.Series(s).dropna()
    if len(s) == 0: return dict(net=0.0, Sharpe=0.0, maxDD=0.0, Calmar=0.0, n=0)
    eq = (1+s).cumprod(); dd = float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu = s.mean()*ann; vol = s.std()*np.sqrt(ann); shp = mu/vol if vol > 0 else 0.0
    cagr = (eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round(float((eq.iloc[-1]-1)*100), 1), Sharpe=round(float(shp), 2), maxDD=round(dd, 1),
                Calmar=round(float(cagr/abs(dd)), 2) if dd else 0.0, n=int(len(s)))
def jackknife(s):
    s = pd.Series(s).dropna(); yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    return round(max(perm_p(s[s.index.year != y]) for y in yrs), 3)
def walkforward(s, k=5):
    s = pd.Series(s).dropna(); n = len(s); b = [int(n*i/k) for i in range(k+1)]
    return sum(1 for i in range(k) if (1+s.iloc[b[i]:b[i+1]]).prod()-1 > 0)
def block_bootstrap(s, n_paths=N_PATHS, horizon=None, block=4, seed=SEED):
    w = pd.Series(s).dropna().values; n = len(w)
    if n == 0: return np.zeros((n_paths, 1))
    horizon = horizon or n
    rng = np.random.default_rng(seed); P = np.empty((n_paths, horizon))
    for p in range(n_paths):
        seq = []
        while len(seq) < horizon:
            st = rng.integers(0, n); seq.extend(w[(st+k) % n] for k in range(block))
        P[p] = seq[:horizon]
    return P
def p95_maxdd(P):
    mdd = np.zeros(len(P))
    for i in range(len(P)):
        eq = np.cumprod(1+P[i]); peak = np.maximum.accumulate(eq); mdd[i] = ((eq-peak)/peak).min()
    return round(float(np.percentile(mdd, 5))*100, 1)

def run():
    selftest = os.environ.get("EDGE18_SELFTEST") == "1"
    have = [p for p in NEW4 if H1C(p) is not None]
    print(("⚠ SELFTEST(合成データ・実判定不可)\n" if selftest else "") +
          f"edge18 v7横展開 H1正式検証 | 銘柄={have} α={ALPHA}")
    if len(have) < 3:
        print("[STOP] 新4クロスのH1が3本未満。④データ取得セルを実行してください。"); return None
    s = basket_weekly(have)
    st = stat(s); pp = round(perm_p(s), 4)
    jk = jackknife(s)
    h = len(s)//2; IS = float((1+s.iloc[:h]).prod()-1)*100; OOS = float((1+s.iloc[h:]).prod()-1)*100
    wf = walkforward(s)
    cost2 = stat(basket_weekly(have, cost_pip=COST_PIP*2))["net"]
    ddp95 = p95_maxdd(block_bootstrap(s))
    # G4 プラセボ: 火〜金は非有意・月曜のみ有意
    plc = {wd: round(perm_p(basket_weekly(have, weekday=wd)), 3) for wd in (1, 2, 3, 4)}
    g4 = (pp < 0.05) and all(v > 0.05 for v in plc.values())
    # 参考ρ(既存v7 3クロスがDriveにあれば)
    v7s = basket_weekly([p for p in YEN3 if H1C(p) is not None])
    rho = None
    if len(v7s) > 50:
        j = pd.concat([s.rename("x"), v7s.rename("v")], axis=1).dropna()
        rho = round(float(j["x"].corr(j["v"])), 2)
    yrs = (s.index.max()-s.index.min()).days/365.25
    G = dict(G1_10y=yrs >= 8.5, G2_nolook_cost=True, G3_perm_bonf=pp < ALPHA, G4_placebo=bool(g4),
             G5_jackknife=(jk is not None and jk <= 0.10), G6_IS_OOS=(IS > 0 and OOS > 0),
             G7_walkforward=wf >= 4, G8_cost=cost2 > 0, G9_DDfit=ddp95 >= -10.0)
    core = [G["G3_perm_bonf"], G["G4_placebo"], G["G5_jackknife"], G["G6_IS_OOS"],
            G["G7_walkforward"], G["G8_cost"], G["G9_DDfit"]]
    if all(core): verdict = "ADOPT (v7同格)"
    elif G["G4_placebo"] and G["G6_IS_OOS"] and G["G7_walkforward"] and G["G8_cost"]:
        verdict = "STRONG-LEAD (Bonf/JKのみ未達)"
    else: verdict = "LEAD/REJECT(コア複数未達)"
    out = dict(pairs=have, years=round(yrs, 1), stat=st, perm_p=pp, alpha=ALPHA, jackknife_max=jk,
               IS_pct=round(IS, 1), OOS_pct=round(OOS, 1), wf=f"{wf}/5", cost2x_net=cost2,
               dd_p95=ddp95, placebo_weekdays_p=plc, rho_to_v7=rho, gates=G,
               gates_passed=f"{sum(bool(v) for v in G.values())}/9", verdict=verdict, selftest=selftest)
    print(f"\n### edge18 [{verdict}] {out['gates_passed']}")
    print(f"  net {st['net']}% Sharpe {st['Sharpe']} maxDD {st['maxDD']}% Calmar {st['Calmar']} n={st['n']}週 span {out['years']}y")
    print(f"  perm_p={pp}(α{ALPHA}:{G['G3_perm_bonf']}) JKmax={jk}({G['G5_jackknife']}) IS {out['IS_pct']}%/OOS {out['OOS_pct']}%({G['G6_IS_OOS']}) WF {out['wf']}({G['G7_walkforward']})")
    print(f"  2×cost net {cost2}%({G['G8_cost']}) | p95maxDD {ddp95}%({G['G9_DDfit']}) | 火-金プラセボp {plc}(G4:{G['G4_placebo']})")
    print(f"  参考ρ(既存v7): {rho}")
    drive_ok = os.path.exists("/content/drive/MyDrive")
    path = (H1_DIR.format(base=DRIVE_BASE) + "/edge18_v7x_h1.json") if drive_ok else "research/results/edge18_v7x_h1.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存:", path)
    return out

if __name__ == "__main__":
    run()
