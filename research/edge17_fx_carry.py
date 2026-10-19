"""
edge17_fx_carry.py — FXキャリー(G10金利ランキング)【事前登録 docs/92】。
毎月末: 3M金利(2ヶ月ラグ)で8通貨をランク → 上位2 LONG/下位2 SHORT(各25%, 対USDペア, USD枠=現金)。
ゲート: dir / perm<=0.05 / JK<=0.10 / split強化(両期間+かつ2016+>=全期間×0.3) / |ρv7|<=0.4 /
placebo(ランダムランキング) / cost(1/2/4pip)。STRONG-LEAD=全通過 / LEAD=net>0&p<=0.10 / 他REJECT。
"""
import os, json, importlib.util
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location("e13", "research/edge13_longhistory_confirm.py")
e13 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e13)

FRED = {"USD": "TB3MS", "JPY": "IR3TIB01JPM156N", "EUR": "IR3TIB01EZM156N", "GBP": "IR3TIB01GBM156N",
        "AUD": "IR3TIB01AUM156N", "CAD": "IR3TIB01CAM156N", "CHF": "IR3TIB01CHM156N", "NZD": "IR3TIB01NZM156N"}
# 通貨→(Yahooペア名, LONG通貨=ペアLONGか)
PAIRS = {"EUR": ("EURUSD", +1), "GBP": ("GBPUSD", +1), "AUD": ("AUDUSD", +1), "NZD": ("NZDUSD", +1),
         "JPY": ("USDJPY", -1), "CHF": ("USDCHF", -1), "CAD": ("USDCAD", -1)}
_YH = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
       "USDJPY": "JPY=X", "USDCHF": "CHF=X", "USDCAD": "CAD=X"}
LOCAL = "./research/data"

def rates():
    out = {}
    for ccy, sid in FRED.items():
        path = f"{LOCAL}/rate_{ccy}.csv"
        if not os.path.exists(path):
            df = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
            df.to_csv(path, index=False)
        df = pd.read_csv(path)
        s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                      index=pd.PeriodIndex(pd.to_datetime(df.iloc[:, 0]), freq="M")).dropna()
        out[ccy] = s
    return pd.DataFrame(out)

def fx_monthly():
    out = {}
    for pair, yh in _YH.items():
        path = f"{LOCAL}/{pair}_carry_d.csv"
        if not os.path.exists(path):
            import yfinance as yf
            df = yf.download(yh, start="1995-01-01", end="2026-06-01", progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df[["Close"]].rename(columns={"Close": "close"}).to_csv(path, index_label="date")
        df = pd.read_csv(path)
        s = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"])).dropna()
        m = s.groupby(s.index.to_period("M")).last()
        out[pair] = m
    return pd.DataFrame(out)

def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())

def carry_series(R, FXm, pip_cost=2.0, placebo=False, seed=7):
    rng = np.random.default_rng(seed)
    ret = FXm.pct_change()
    months = [m for m in FXm.index if m in R.index]
    legs = {}
    for i in range(len(months)-1):
        m, nxt = months[i], months[i+1]
        lag = m - 2
        if lag not in R.index: continue
        row = R.loc[lag].dropna()
        if len(row) < 6: continue
        order = list(row.sort_values(ascending=False).index)
        if placebo: order = list(rng.permutation(order))
        top, bot = order[:2], order[-2:]
        pnl, nlegs = 0.0, 0
        for ccy, sgn in [(c, +1) for c in top] + [(c, -1) for c in bot]:
            if ccy == "USD": continue
            pair, side = PAIRS[ccy]
            r1 = ret.at[nxt, pair] if pair in ret.columns else np.nan
            px = FXm.at[m, pair]
            if not (np.isfinite(r1) and np.isfinite(px)): continue
            pipsz = 0.01 if pair.endswith("JPY") else 0.0001
            cost = pip_cost*pipsz/px
            pnl += 0.25*(sgn*side*r1 - cost); nlegs += 1
        if nlegs > 0: legs[nxt.to_timestamp("M")] = pnl
    return pd.Series(legs).sort_index()

def stats(x):
    x = pd.Series(x).dropna()
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round(float(eq.iloc[-1]-1)*100, 1), maxDD_pct=round(float(dd), 1),
                worst_month=round(float(x.min())*100, 2), n=int(len(x)),
                mean_yr=round(float(x.mean())*12*100, 2))

R = rates(); FXm = fx_monthly()
s = carry_series(R, FXm)
st = stats(s); p = round(perm_p(s.values), 4)
yrs = sorted(set(s.index.year))
jk = round(max(perm_p(s[s.index.year != y].values) for y in yrs), 3)
pre, post = s[s.index < "2016-01-01"], s[s.index >= "2016-01-01"]
ym = e13.v7_proxy(); ymm = ym.groupby(ym.index.to_period("M")).sum() if not hasattr(ym.index, "to_timestamp") else ym
cm = s.groupby(s.index.to_period("M")).sum()
j = pd.concat([cm.rename("c"), ym.rename("y")], axis=1).dropna()
rho = round(float(j["c"].corr(j["y"])), 2) if len(j) > 24 else None
plc = carry_series(R, FXm, placebo=True)
plc_net = stats(plc)["net_pct"]; plc_p = round(perm_p(plc.values), 3)
cost = {f"{c}pip": stats(carry_series(R, FXm, pip_cost=float(c)))["net_pct"] for c in (1, 2, 4)}

g_dir = st["net_pct"] > 0
g_perm = p <= 0.05
g_jk = jk <= 0.10
full_m, post_m = float(s.mean()), float(post.mean())
g_split = (float(pre.mean()) > 0 and post_m > 0 and post_m >= 0.3*full_m)
g_indep = (rho is None) or abs(rho) <= 0.4
g_plac = (plc_p > 0.05 and st["net_pct"] > plc_net)
g_cost = all(v > 0 for v in cost.values())
passed = sum([g_dir, g_perm, g_jk, g_split, g_indep, g_plac, g_cost])
verdict = "STRONG-LEAD" if passed == 7 else ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")

print(f"### edge17 FXキャリー → {verdict} ({passed}/7)")
print(f"  期間 {s.index[0].date()}〜{s.index[-1].date()} n={st['n']}ヶ月")
print(f"  net {st['net_pct']}% 年平均{st['mean_yr']}% maxDD {st['maxDD_pct']}% 最悪月 {st['worst_month']}%")
print(f"  p={p}({g_perm}) JKmax={jk}({g_jk}) | pre平均{pre.mean()*1200:.2f}%/年 2016+平均{post.mean()*1200:.2f}%/年 split強化:{g_split}")
print(f"  ρv7={rho}({g_indep}) | placebo net{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")

out = dict(**st, perm_p=p, jk_max=jk, pre_mean_yr=round(float(pre.mean())*1200, 2),
           post_mean_yr=round(float(post.mean())*1200, 2), rho_v7=rho,
           placebo=dict(net=plc_net, p=plc_p), cost=cost,
           gates=dict(dir=bool(g_dir), perm=bool(g_perm), jk=bool(g_jk), split=bool(g_split),
                      indep=bool(g_indep), placebo=bool(g_plac), cost=bool(g_cost)),
           yearly={int(y): round(float((1+s[s.index.year == y]).prod()-1)*100, 1) for y in yrs},
           verdict=verdict)
os.makedirs("research/results", exist_ok=True)
with open("research/results/edge17_fx_carry.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("保存: research/results/edge17_fx_carry.json")
