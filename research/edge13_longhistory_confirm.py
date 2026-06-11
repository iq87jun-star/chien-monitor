"""
edge13_longhistory_confirm.py — 長期履歴確認【事前登録 docs/83】。
凍結済みルール(v7日足近似/E-Mon/E5)を2016年以前に適用する確認的検定。新仮説・新パラメタなし。

採点(docs/83 §1): A=pre-2016窓(net>0 かつ perm_p<=0.0167) /
  B=全期間窓(perm_p<=0.001 かつ 年次JK<=0.10 かつ 5年ブロック全net>0)。
昇格(§2): A&B=ADOPT候補(Yahoo近似) / Aのみ=STRONG-LEAD(長期確認済) / A不合格=昇格なし(正直に記録)。
"""
import os, json, hashlib, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

LOCAL = "./research/data"
END = "2026-06-01"
PRE_END = "2016-01-01"
ALPHA_PRE, ALPHA_FULL = 0.05/3, 0.001

_YH = {"USDJPY": "JPY=X", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
       "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "XAUUSD": "GC=F"}
YEN = ["USDJPY", "EURJPY", "GBPJPY"]
EQ  = ["US500", "NAS100", "GER40"]
E5A = ["XAUUSD", "US500", "NAS100", "GER40"]

CACHE = {}
def daily(name):
    if name in CACHE: return CACHE[name]
    os.makedirs(LOCAL, exist_ok=True)
    path = f"{LOCAL}/{name}_lh_d.csv"
    if not os.path.exists(path):
        import yfinance as yf
        df = yf.download(_YH[name], start="1985-01-01", end=END, progress=False, auto_adjust=False)
        if df is None or len(df) == 0: raise RuntimeError(f"download failed: {name}")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df[["Close"]].rename(columns={"Close": "close"}).to_csv(path, index_label="date")
    df = pd.read_csv(path)
    s = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"])).dropna().sort_index()
    CACHE[name] = s
    return s

def sha(name):
    h = hashlib.sha256()
    with open(f"{LOCAL}/{name}_lh_d.csv", "rb") as f: h.update(f.read())
    return h.hexdigest()[:16]

# ---- 統計(edge11と同一) ----
def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())
def perm_p_robust(s, n=3000, seed=13):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    return perm_p(s.groupby(s.index.to_period("M")).sum().values, n=n, seed=seed)
def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0, cagr_pct=0, sharpe=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    yrs = (x.index[-1]-x.index[0]).days/365.25
    cagr = (float(eq.iloc[-1])**(1/yrs)-1)*100 if yrs > 1 and eq.iloc[-1] > 0 else 0
    m = x.groupby(x.index.to_period("M")).sum()
    sh = float(m.mean()/m.std()*np.sqrt(12)) if len(m) > 12 and m.std() > 0 else 0
    return dict(net_pct=round((float(eq.iloc[-1])-1)*100, 1), win_pct=round(float((x > 0).mean())*100, 0),
                maxDD_pct=round(float(dd), 1), n=int(len(x)), cagr_pct=round(cagr, 1), sharpe=round(sh, 2))
def jackknife_max(s):
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    return round(max(perm_p_robust(s[s.index.year != y]) for y in yrs), 3)
def blocks5y(s):
    out = {}
    for y0 in range(s.index[0].year//5*5, s.index[-1].year+1, 5):
        b = s[(s.index.year >= y0) & (s.index.year < y0+5)]
        if len(b) > 20: out[f"{y0}-{y0+4}"] = stats(b)["net_pct"]
    return out

# ---- 凍結ルール(edge6/edge11実装と同一) ----
def monday_legs(assets, fx, window="canonical"):
    """window='canonical'=月曜終値→翌営業日終値(edge11 yen_monday_monthly/ea_benchmarkと同一のshift(-1))。
    window='prereg_aswritten'=前営業日終値→月曜終値(docs/83初版の誤記載=週末ギャップ窓。比較記録用)。"""
    legs = []
    for a in assets:
        s = daily(a)
        r = s.pct_change().shift(-1) if window == "canonical" else s.pct_change()
        c = (2.0*0.01/s) if fx else pd.Series(5e-4, index=s.index)
        mon = np.where(s.index.dayofweek == 0)[0]
        for i in mon:
            if i == 0 or not np.isfinite(r.iloc[i]): continue
            legs.append((s.index[i], float(r.iloc[i]) - float(c.iloc[i])))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).mean().sort_index()

def v7_proxy():  return monday_legs(YEN, fx=True)
def emon():      return monday_legs(EQ, fx=False)
def v7_proxy_gapwin():  return monday_legs(YEN, fx=True, window="prereg_aswritten")
def emon_gapwin():      return monday_legs(EQ, fx=False, window="prereg_aswritten")

def e5():
    rets, sigs, ws = {}, {}, {}
    for a in E5A:
        d = daily(a); m = d.groupby(d.index.to_period("M")).last(); m.index = m.index.to_timestamp("M")
        comp = sum(np.sign(m.pct_change(L)) for L in (1, 3, 6, 12)); pos = np.sign(comp)
        r = m.pct_change()
        rets[a] = r.shift(-1); sigs[a] = pos; ws[a] = 1.0/r.rolling(12, min_periods=6).std()
    idx = sorted(set().union(*[set(x.index) for x in sigs.values()]))
    out = {}
    for t in idx:
        num, den = 0.0, 0.0
        for a in rets:
            p0 = sigs[a].get(t, 0); w = ws[a].get(t, np.nan); nx = rets[a].get(t, np.nan)
            if not (np.isfinite(p0) and p0 != 0 and np.isfinite(w) and np.isfinite(nx)): continue
            num += w*(p0*nx - 5e-4); den += w
        if den > 0: out[t] = num/den
    s = pd.Series(out).sort_index().dropna()
    return s[s.index >= "2000-09-30"]   # 金(GC=F)開始後のみ=docs/83の窓

def run():
    for k in _YH: daily(k)
    out = {"meta": dict(alpha_pre=round(ALPHA_PRE, 4), alpha_full=ALPHA_FULL, end=END,
                        inputs={k: sha(k) for k in _YH},
                        spans={k: [str(daily(k).index[0].date()), str(daily(k).index[-1].date())]
                               for k in _YH}), "edges": {}}
    for name, fn in [("v7_proxy", v7_proxy), ("E-Mon", emon), ("E5", e5),
                     ("v7_proxy_gapwin(誤窓・記録用)", v7_proxy_gapwin),
                     ("E-Mon_gapwin(誤窓・記録用)", emon_gapwin)]:
        s = fn()
        pre, full = s[s.index < PRE_END], s
        st_pre, st_full = stats(pre), stats(full)
        p_pre, p_full = round(perm_p_robust(pre), 4), round(perm_p_robust(full), 4)
        jk = jackknife_max(full); blk = blocks5y(full)
        gA = st_pre["net_pct"] > 0 and p_pre <= ALPHA_PRE
        gB = p_full <= ALPHA_FULL and (jk is not None and jk <= 0.10) and all(v > 0 for v in blk.values())
        verdict = "ADOPT候補(Yahoo近似)" if (gA and gB) else \
                  ("STRONG-LEAD(長期確認済)" if gA else "昇格なし(pre窓不合格)")
        out["edges"][name] = dict(pre=dict(**st_pre, perm_p=p_pre, span=[str(pre.index[0].date()), str(pre.index[-1].date())] if len(pre) else None),
                                  full=dict(**st_full, perm_p=p_full, jk_max=jk, blocks5y=blk),
                                  gate_A=gA, gate_B=gB, verdict=verdict)
        print(f"\n### {name} → {verdict}")
        print(f"  pre-2016: span={out['edges'][name]['pre']['span']} net{st_pre['net_pct']}% CAGR{st_pre['cagr_pct']}% "
              f"maxDD{st_pre['maxDD_pct']}% Sh{st_pre['sharpe']} n={st_pre['n']} p={p_pre}(α{round(ALPHA_PRE,4)}:{gA and st_pre['net_pct']>0})")
        print(f"  全期間 : net{st_full['net_pct']}% CAGR{st_full['cagr_pct']}% maxDD{st_full['maxDD_pct']}% "
              f"Sh{st_full['sharpe']} p={p_full}(α{ALPHA_FULL}) JKmax={jk} blocks={blk} → B:{gB}")
    os.makedirs("research/results", exist_ok=True)
    with open("research/results/edge13_longhistory_confirm.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge13_longhistory_confirm.json")
    return out

if __name__ == "__main__":
    run()
