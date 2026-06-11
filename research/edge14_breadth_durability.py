"""
edge14_breadth_durability.py — 残りエッジの検証強化【事前登録 docs/85】。
H14a v4耐久性(履歴拡張) / H14b G3耐久性(FOMC 1994-2015) / H14c v7横展開(未検定JPYクロス) /
H14d E-Mon横展開(未検定株指)。N=4 → α=0.0125。各 ①net>0 ②perm_p_robust<=0.0125。
耐久性はサニティ(2016+窓が正)を前提、5年ブロック符号を記録(判定外)。
"""
import os, json, hashlib, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

LOCAL = "./research/data"
END = "2026-06-01"; PRE_END = "2016-01-01"
ALPHA = 0.05/4

_YH = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X", "AUDUSD": "AUDUSD=X",
       "USDCHF": "CHF=X", "USDCAD": "CAD=X", "NZDUSD": "NZDUSD=X", "EURJPY": "EURJPY=X",
       "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "NZDJPY": "NZDJPY=X", "CADJPY": "CADJPY=X",
       "CHFJPY": "CHFJPY=X", "US500": "^GSPC", "JP225": "^N225", "UK100": "^FTSE", "FR40": "^FCHI"}
V4_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
V7_NEW   = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
EMON_NEW = ["JP225", "UK100", "FR40"]

FOMC_PRE = []  # docs/85 §3(1994-2015 定例176回)
_F = {1994:"2/4,3/22,5/17,7/6,8/16,9/27,11/15,12/20",1995:"2/1,3/28,5/23,7/6,8/22,9/26,11/15,12/19",
1996:"1/31,3/26,5/21,7/3,8/20,9/24,11/13,12/17",1997:"2/5,3/25,5/20,7/2,8/19,9/30,11/12,12/16",
1998:"2/4,3/31,5/19,7/1,8/18,9/29,11/17,12/22",1999:"2/3,3/30,5/18,6/30,8/24,10/5,11/16,12/21",
2000:"2/2,3/21,5/16,6/28,8/22,10/3,11/15,12/19",2001:"1/31,3/20,5/15,6/27,8/21,10/2,11/6,12/11",
2002:"1/30,3/19,5/7,6/26,8/13,9/24,11/6,12/10",2003:"1/29,3/18,5/6,6/25,8/12,9/16,10/28,12/9",
2004:"1/28,3/16,5/4,6/30,8/10,9/21,11/10,12/14",2005:"2/2,3/22,5/3,6/30,8/9,9/20,11/1,12/13",
2006:"1/31,3/28,5/10,6/29,8/8,9/20,10/25,12/12",2007:"1/31,3/21,5/9,6/28,8/7,9/18,10/31,12/11",
2008:"1/30,3/18,4/30,6/25,8/5,9/16,10/29,12/16",2009:"1/28,3/18,4/29,6/24,8/12,9/23,11/4,12/16",
2010:"1/27,3/16,4/28,6/23,8/10,9/21,11/3,12/14",2011:"1/26,3/15,4/27,6/22,8/9,9/21,11/2,12/13",
2012:"1/25,3/13,4/25,6/20,8/1,9/13,10/24,12/12",2013:"1/30,3/20,5/1,6/19,7/31,9/18,10/30,12/18",
2014:"1/29,3/19,4/30,6/18,7/30,9/17,10/29,12/17",2015:"1/28,3/18,4/29,6/17,7/29,9/17,10/28,12/16"}
for y, ds in _F.items():
    for md in ds.split(","):
        m, d = md.split("/"); FOMC_PRE.append(f"{y}-{int(m):02d}-{int(d):02d}")
FOMC_POST = [  # docs/81 §5(2016-2026)
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

CACHE = {}
def ohlc(name):
    if name in CACHE: return CACHE[name]
    os.makedirs(LOCAL, exist_ok=True)
    path = f"{LOCAL}/{name}_lh_ohlc.csv"
    if not os.path.exists(path):
        import yfinance as yf
        df = yf.download(_YH[name], start="1985-01-01", end=END, progress=False, auto_adjust=False)
        if df is None or len(df) == 0: raise RuntimeError(f"download failed: {name}")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df[["Open","High","Low","Close"]].rename(columns=str.lower).to_csv(path, index_label="date")
    df = pd.read_csv(path, index_col="date", parse_dates=True).dropna().sort_index()
    df = df[(df.index.dayofweek <= 4) & (df["close"] > 0)]
    CACHE[name] = df
    return df

def sha(name):
    h = hashlib.sha256()
    with open(f"{LOCAL}/{name}_lh_ohlc.csv", "rb") as f: h.update(f.read())
    return h.hexdigest()[:16]

def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
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
    if len(x) == 0: return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round(float(eq.iloc[-1]-1)*100, 1), win_pct=round(float((x > 0).mean())*100, 0),
                maxDD_pct=round(float(dd), 1), n=int(len(x)))
def blocks5y(s):
    out = {}
    for y0 in range(int(s.index[0].year)//5*5, int(s.index[-1].year)+1, 5):
        b = s[(s.index.year >= y0) & (s.index.year < y0+5)]
        if len(b) > 10: out[f"{y0}-{y0+4}"] = stats(b)["net_pct"]
    return out

# ---- ea_benchmark_10y.py から逐語移植(凍結ルール) ----
def rsi_w(c, n=14):
    d = np.diff(c, prepend=c[0]); up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1.0/n
    for i in range(1, len(c)): au[i] = a*up[i]+(1-a)*au[i-1]; ad[i] = a*dn[i]+(1-a)*ad[i-1]
    return 100 - 100/(1 + au/np.where(ad == 0, 1e-12, ad))
def atr_d(h, l, c, n=14):
    pc = np.roll(c, 1); pc[0] = c[0]; tr = np.maximum(h-l, np.maximum(np.abs(h-pc), np.abs(l-pc)))
    o = np.empty_like(tr); o[0] = tr[0]; a = 1.0/n
    for i in range(1, len(tr)): o[i] = a*tr[i]+(1-a)*o[i-1]
    return o

def v4_daily_legs():
    """v4 k>=4 合議・逆張り(ea_benchmark v4_series 逐語・kmin=4)。日付índex の取引リターン系列。"""
    legs = []
    for p in V4_PAIRS:
        df = ohlc(p); o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c); rsi = rsi_w(c, 14); atr = atr_d(h, l, c, 14); bb = 20; cost = 2*pip(p)
        i = bb + 2
        while i < n - 1:
            win = c[i-bb:i]; mean = win.mean(); sd = win.std(ddof=1); z = (c[i]-mean)/sd if sd > 0 else 0.0
            down = 0
            for k in range(12):
                if i-k-1 >= 0 and c[i-k] < c[i-k-1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i-k-1 >= 0 and c[i-k] > c[i-k-1]: up += 1
                else: break
            ret = (c[i]-c[i-1])/c[i-1] if c[i-1] else 0.0; mv = 0.005
            buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(ret < -mv)
            sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(ret > mv)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0: i += 1; continue
            entry = o[i+1]; sld = 1.5*atr[i]; tpd = 1.2*sld
            if sld <= 0 or entry <= 0: i += 1; continue
            sl = entry - sig*sld; tp = entry + sig*tpd; ex = None; j = i+1; held = 0
            while j < n and held < 8:
                if sig > 0:
                    if l[j] <= sl: ex = sl; break
                    if h[j] >= tp: ex = tp; break
                else:
                    if h[j] >= sl: ex = sl; break
                    if l[j] <= tp: ex = tp; break
                j += 1; held += 1
            if ex is None: ex = c[min(j, n-1)]
            legs.append((idx[min(j, n-1)], sig*(ex/entry-1.0) - cost/entry))
            i = max(i+1, j)
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).sum().sort_index()

def fomc_proxy_legs(dates):
    """G3日足近似: 声明日T → close(T-2)→close(T-1) LONG, 5bps。"""
    df = ohlc("US500"); c = df["close"]; idx = df.index
    legs = []
    for d in dates:
        t = pd.Timestamp(d)
        pos = idx.searchsorted(t)
        if pos >= len(idx) or pos < 2: continue
        if idx[pos] != t:  # 声明日が休場(無いはず)→直前営業日基準
            pos = pos
        i1, i0 = pos-1, pos-2
        legs.append((idx[i0], float(c.iloc[i1]/c.iloc[i0] - 1.0) - 5e-4))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).mean().sort_index()

def monday_legs(assets, fx, start="2016-01-01"):
    legs = []
    for a in assets:
        s = ohlc(a)["close"]; s = s[s.index >= start]
        r = s.pct_change().shift(-1)
        c = (2.0*pip(a)/s) if fx else pd.Series(5e-4, index=s.index)
        mon = np.where(s.index.dayofweek == 0)[0]
        for i in mon:
            if not np.isfinite(r.iloc[i]): continue
            legs.append((s.index[i], float(r.iloc[i]) - float(c.iloc[i])))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).mean().sort_index()

def judge(name, s, sanity=None):
    st = stats(s); p = round(perm_p_robust(s), 4)
    ok = st["net_pct"] > 0 and p <= ALPHA
    res = dict(**st, perm_p=p, passed=bool(ok), blocks5y=blocks5y(s) if len(s) > 50 else None,
               span=[str(s.index[0].date()), str(s.index[-1].date())] if len(s) else None)
    if sanity is not None: res["sanity_2016plus_net"] = sanity
    print(f"\n### {name} → {'合格' if ok else '不合格'}")
    print(f"  span={res['span']} net{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} p={p}(α{ALPHA})")
    if res.get("blocks5y"): print(f"  blocks={res['blocks5y']}")
    if sanity is not None: print(f"  サニティ(2016+同実装): net{sanity}%")
    return res

def run():
    for k in _YH: ohlc(k)
    out = {"meta": dict(alpha=ALPHA, end=END, n_fomc_pre=len(FOMC_PRE),
                        inputs={k: sha(k) for k in _YH})}
    v4 = v4_daily_legs()
    v4_pre, v4_post = v4[v4.index < PRE_END], v4[v4.index >= PRE_END]
    out["H14a_v4_durability"] = judge("H14a v4耐久性(pre-2016)", v4_pre, sanity=stats(v4_post)["net_pct"])
    g3_pre = fomc_proxy_legs(FOMC_PRE)
    g3_post = fomc_proxy_legs(FOMC_POST)
    out["H14b_g3_durability"] = judge("H14b G3耐久性(FOMC 1994-2015)", g3_pre, sanity=stats(g3_post)["net_pct"])
    out["H14c_v7_breadth"] = judge("H14c v7横展開(AUD/NZD/CAD/CHF JPY 2016+)", monday_legs(V7_NEW, fx=True))
    out["H14d_emon_breadth"] = judge("H14d E-Mon横展開(JP225/UK100/FR40 2016+)", monday_legs(EMON_NEW, fx=False))
    os.makedirs("research/results", exist_ok=True)
    with open("research/results/edge14_breadth_durability.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge14_breadth_durability.json")
    return out

if __name__ == "__main__":
    run()
