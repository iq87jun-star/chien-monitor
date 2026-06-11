"""
edge11_fable5_batch_10y.py — Fable 5 新手法バッチ【事前登録 docs/79】の10年検定。

事前登録5候補(N=5, Bonferroni α=0.05/5=0.01):
  F1_EQ_TOM       : 株式ターン・オブ・マンス(月末T-1終値→翌月T+3終値 LONG, US500/NAS100/GER40)
  F2_VIX_TS_GATE  : VIX期間構造ゲート(VIX3M>VIX=コンタンゴの翌日だけUS500保有, フリップ時のみコスト)
  F3_UST2JPY      : 前月Δ米10年金利符号→翌月USDJPYを同方向に1ヶ月保有
  F4_JPY_FISCAL   : 3/15以降初営業日終値→3月末終値 円クロスSHORT(リパトリ円高)
  F5_GOLD_WEEKEND : 金 金曜終値→翌営業日終値 LONG(週末リスクプレミアム)
  PLC: F1/F5=同方向ランダム・カレンダー配置 / F2=ON比率保存ランダムマスク / F3/F4=同機会ランダム方向

ゲート(edge6と同一): G_perm 頑健p<=0.01 / G_jk JKmax<=0.10 / G_oos IS・OOS両+ /
  G_indep v7日足近似との月次相関|ρ|<=0.4 / G_plac プラセボ非有意かつ候補>プラセボ / G_cost 2-20bpsで+
ADOPT=G_perm,G_jk,G_oos,G_indep,G_plac全通過 / LEAD=net>0かつ頑健p<=0.10 / 他REJECT。

データ: Yahoo日足 2016-01-01〜2026-06-01 を research/data/<NAME>_d.csv にキャッシュ(gitignore済)。
⚠ Yahoo近似・配当/スワップ未調整。LEAD以上はDrive(Dukascopy/配当込みCFD)で要追検(docs/19)。
"""
import os, json, hashlib, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

LOCAL = "./research/data"
START, END = "2016-01-01", "2026-06-01"
BASE_BPS = 5.0
BONF = 0.05 / 5

_YH = {"XAUUSD": "GC=F", "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI",
       "VIX": "^VIX", "VIX3M": "^VIX3M", "UST10Y": "^TNX",
       "USDJPY": "JPY=X", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X"}
YEN = ["USDJPY", "EURJPY", "GBPJPY"]
EQ  = ["US500", "NAS100", "GER40"]

def _isfx(a): return a in YEN
def pip(a): return 0.01  # 全FXがJPYクロス

CACHE = {}
def daily_close(name):
    if name in CACHE: return CACHE[name]
    os.makedirs(LOCAL, exist_ok=True)
    path = f"{LOCAL}/{name}_d.csv"
    if not os.path.exists(path):
        import yfinance as yf
        df = yf.download(_YH[name], start=START, end=END, progress=False, auto_adjust=False)
        if df is None or len(df) == 0: raise RuntimeError(f"download failed: {name}")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df[["Close"]].rename(columns={"Close": "close"}).to_csv(path, index_label="date")
    df = pd.read_csv(path)
    s = pd.Series(df["close"].astype(float).values,
                  index=pd.to_datetime(df["date"])).dropna().sort_index()
    CACHE[name] = s
    return s

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f: h.update(f.read())
    return h.hexdigest()[:16]

# ---------- 統計ハーネス(edge6と同一) ----------
def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())
def perm_p_robust(s, n=3000, seed=13):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    ms = s.groupby(s.index.to_period("M")).sum()
    return perm_p(ms.values, n=n, seed=seed)
def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100, 1), win_pct=round((x > 0).mean()*100, 0),
                maxDD_pct=round(dd, 1), n=int(len(x)))
def jackknife(s):
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    jk = {int(y): round(perm_p_robust(s[s.index.year != y]), 3) for y in yrs}
    return jk, round(max(jk.values()), 3)
def mP(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

def yen_monday_monthly():
    """v7基準(円月曜LONG)の日足近似: 月曜終値→翌営業日終値、2pip控除、3クロス平均→月次合算。"""
    legs = []
    for p in YEN:
        s = daily_close(p); r = s.pct_change().shift(-1)
        c = 2.0*pip(p)/s
        mon = s.index[s.index.dayofweek == 0]
        for t in mon:
            v = r.get(t, np.nan)
            if np.isfinite(v): legs.append((t, v - c[t]))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    s = s.groupby(s.index).mean().sort_index()
    return mP(s)

def _series_from(legs):
    if not legs: return pd.Series(dtype=float)
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).mean().sort_index()

def _window_ret(s, i0, i1, bps, fx=False):
    """終値i0→終値i1の保有リターン、往復コスト控除。"""
    r = s.iloc[i1]/s.iloc[i0] - 1.0
    c = (2.0*0.01/s.iloc[i0]) if fx else bps/1e4
    return r, c

# ---------- F1 株式ターン・オブ・マンス ----------
def f1_eq_tom(bps=BASE_BPS, placebo=False, seed=1):
    rng = np.random.default_rng(seed); legs = []
    for a in EQ:
        s = daily_close(a); per = s.index.to_period("M")
        months = sorted(set(per))
        for k in range(len(months)-1):
            cur = np.where(per == months[k])[0]; nxt = np.where(per == months[k+1])[0]
            if len(cur) < 5 or len(nxt) < 4: continue
            i0, i1 = cur[-2], nxt[2]           # 月末T-1終値 → 翌月3営業日目終値
            if placebo:                          # 同方向・同保有長のランダム配置(月中)
                span = i1 - i0
                lo, hi = cur[3], cur[-2]-span if cur[-2]-span > cur[3] else cur[3]+1
                i0 = int(rng.integers(lo, hi)); i1 = i0 + span
                if i1 >= len(s): continue
            r, c = _window_ret(s, i0, i1, bps)
            legs.append((s.index[i0], r - c))
    return _series_from(legs)

# ---------- F2 VIX期間構造ゲート ----------
def f2_vix_ts_gate(bps=BASE_BPS, placebo=False, seed=2):
    rng = np.random.default_rng(seed)
    px = daily_close("US500"); vix = daily_close("VIX"); v3m = daily_close("VIX3M")
    df = pd.concat({"px": px, "vix": vix, "v3m": v3m}, axis=1).dropna()
    on = (df["v3m"] > df["vix"])
    if placebo:  # ON比率を保ったランダムマスク
        on = pd.Series(rng.random(len(on)) < on.mean(), index=on.index)
    nxt = df["px"].pct_change().shift(-1)
    pos = on.astype(int)
    flips = pos.diff().abs().fillna(0)
    pnl = (pos*nxt - flips*(bps/1e4)/2.0).dropna()  # 往復bpsをフリップ2回で按分
    return pnl[pnl.index < pd.Timestamp(END)]

def f2_n_flips():
    px = daily_close("US500"); vix = daily_close("VIX"); v3m = daily_close("VIX3M")
    df = pd.concat({"px": px, "vix": vix, "v3m": v3m}, axis=1).dropna()
    pos = (df["v3m"] > df["vix"]).astype(int)
    return int(pos.diff().abs().sum()), float(pos.mean())

# ---------- F3 米金利→USDJPYリード ----------
def f3_ust2jpy(bps=BASE_BPS, placebo=False, seed=3):
    rng = np.random.default_rng(seed)
    y = daily_close("UST10Y"); fx = daily_close("USDJPY")
    ym = y.groupby(y.index.to_period("M")).last()
    fxm = fx.groupby(fx.index.to_period("M")).last()
    sig = np.sign(ym.diff())                      # 前月のΔ10年金利符号
    nxt = fxm.pct_change().shift(-1)
    legs = []
    for t in ym.index[:-1]:
        sg = sig.get(t, 0); nx = nxt.get(t, np.nan)
        if not np.isfinite(sg) or sg == 0 or not np.isfinite(nx): continue
        d = rng.choice([-1, 1]) if placebo else sg
        c = 2.0*pip("USDJPY")/fxm[t]
        legs.append((t.to_timestamp("M"), d*nx - c))
    return _series_from(legs)

# ---------- F4 本邦年度末リパトリ ----------
def f4_jpy_fiscal(bps=BASE_BPS, placebo=False, seed=4):
    rng = np.random.default_rng(seed); legs = []
    for a in YEN:
        s = daily_close(a)
        for yr in sorted(set(s.index.year)):
            mar = s[(s.index.year == yr) & (s.index.month == 3)]
            if len(mar) < 12: continue
            half = mar[mar.index.day >= 15]
            if len(half) < 5: continue
            i0 = s.index.get_loc(half.index[0]); i1 = s.index.get_loc(mar.index[-1])
            r, c = _window_ret(s, i0, i1, bps, fx=True)
            d = rng.choice([-1, 1]) if placebo else -1.0   # SHORT(円買い)
            legs.append((s.index[i0], d*r - c))
    return _series_from(legs)

# ---------- F5 金の週末プレミアム ----------
def f5_gold_weekend(bps=BASE_BPS, placebo=False, seed=5):
    rng = np.random.default_rng(seed)
    s = daily_close("XAUUSD"); r = s.pct_change().shift(-1)
    c = bps/1e4
    fri = np.where(s.index.dayofweek == 4)[0]
    if placebo:  # 同方向・同件数のランダム曜日配置(金曜以外)
        pool = np.where(s.index.dayofweek != 4)[0]
        fri = np.sort(rng.choice(pool, size=len(fri), replace=False))
    legs = []
    for i in fri:
        v = r.iloc[i]
        if np.isfinite(v): legs.append((s.index[i], v - c))
    return _series_from(legs)

CAND = {
    "F1_EQ_TOM":       f1_eq_tom,
    "F2_VIX_TS_GATE":  f2_vix_ts_gate,
    "F3_UST2JPY":      f3_ust2jpy,
    "F4_JPY_FISCAL":   f4_jpy_fiscal,
    "F5_GOLD_WEEKEND": f5_gold_weekend,
}

def run():
    ym = yen_monday_monthly()
    nflip, onfrac = f2_n_flips()
    print(f"事前登録N=5 Bonferroniα={BONF} / コスト基準{BASE_BPS}bps / v7基準月数={len(ym)}")
    print(f"F2参考: 10年フリップ回数={nflip} ON比率={onfrac:.2f}")
    out = {"meta": dict(n=5, bonferroni_alpha=BONF, base_bps=BASE_BPS, span=[START, END],
                        f2_flips=nflip, f2_on_frac=round(onfrac, 3),
                        inputs={k: sha256(f"{LOCAL}/{k}_d.csv") for k in _YH}),
           "candidates": {}}
    for name, fn in CAND.items():
        s = fn()
        if len(s) < 24:
            out["candidates"][name] = dict(note="insufficient", n=len(s))
            print(f"\n{name}: データ不足 n={len(s)}"); continue
        st = stats(s); p = round(perm_p_robust(s), 4)
        jk = jackknife(s); jkmax = jk[1] if jk else None
        h = s.index[len(s)//2]; isr, oos = s[s.index < h], s[s.index >= h]
        j = pd.concat([mP(s).rename("c"), ym.rename("y")], axis=1).dropna()
        corr = round(float(j["c"].corr(j["y"])), 2) if len(j) > 12 else None
        plc = fn(placebo=True); plc_p = round(perm_p_robust(plc), 3); plc_net = stats(plc)["net_pct"]
        cost = {f"{c}bps": stats(fn(bps=float(c)))["net_pct"] for c in (2, 5, 10, 20)}
        dd_ok = st["maxDD_pct"] >= -10.0
        g_perm = p <= BONF; g_jk = (jkmax is not None and jkmax <= 0.10)
        g_oos = (isr.sum() > 0 and oos.sum() > 0); g_indep = (corr is None) or abs(corr) <= 0.4
        g_plac = (plc_p > 0.05 and st["net_pct"] > plc_net); g_cost = all(v > 0 for v in cost.values())
        passed = sum([g_perm, g_jk, g_oos, g_indep, g_plac, g_cost])
        grade = "ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac) else \
                ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")
        out["candidates"][name] = dict(**st, perm_p=p, jackknife_max_p=jkmax, jackknife=jk[0] if jk else None,
            IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"], corr_to_v7=corr,
            placebo_net=plc_net, placebo_p=plc_p, cost=cost, dd_within_10pct=dd_ok,
            gates=dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost),
            gates_passed=f"{passed}/6", grade=grade)
        dn = "" if dd_ok else f" ⚠DD{st['maxDD_pct']}%≫-10%=素サイズ不可"
        print(f"\n### {name}  [{grade}] {passed}/6{dn}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p頑健={p}(Bonf{BONF}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts = [n for n, r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads = [n for n, r in out["candidates"].items() if r.get("grade") == "LEAD"]
    print("\n>>> ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 全滅 → Fable 5 バッチでも新エッジ無し(誠実な結論・docs/73系譜に追記)。")
    out["adopted"] = adopts; out["leads"] = leads
    os.makedirs("research/results", exist_ok=True)
    with open("research/results/edge11_fable5_batch_10y.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存: research/results/edge11_fable5_batch_10y.json")
    return out

if __name__ == "__main__":
    run()
