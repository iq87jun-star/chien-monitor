"""
verify_edge10_n5.py — docs/72(edge10) の独立検証。docs/13(v6独立検証)の流儀。

対象: N5_NEARHIGH_52W(ADOPT) を主対象、N2_RATES2JPY(強LEAD) を副対象。
手法(本体 edge10_newaxes_10y.py とはコードパスを分離):
  V1 独立再実装   : legsループでなくベクトル化で N5/N2 月次系列を再構築 → 本体出力と突合(最大絶対差)。
  V2 取引定義変化 : N5 を close→close(本体) と open→open(EA実装と同形) で比較。
  V3 感応度格子   : ratio×lookback の格子で net/maxDD/頑健p — ナイフエッジでないか。
  V4 銘柄分解     : US500/NAS100/GER40 単体での成立性。
  V5 シード安定性 : 頑健順列pをシード20本で分布確認(本体はseed=13の1点)。
  V6 配当込み実証 : SPY/QQQ/EWG の調整後終値(配当込み)で同ルール → 「配当除く指数」近似の頑健性。
  V7 銘柄別タイミングプラセボ: 本体のバスケット近似でなく、各銘柄のON月数を保ったランダム月ロング
     500抽選で DD パーセンタイルを再採点(ベータ識別の厳格版)。
規律: 数字は盛らない。本体と矛盾が出たらそのまま記録する。
"""
import os, json, time, datetime as dt
import urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BASE_BPS = 5.0
P1, P2 = 1451606400, 1767225599
IDX = ["US500", "NAS100", "GER40"]
ETF = {"SPY": "SPY", "QQQ": "QQQ", "EWG": "EWG"}

def load(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_yd.csv"), parse_dates=["t"], index_col="t")
    return df

def fetch_etf(name, sym, tries=5):
    p = os.path.join(DATA, f"{name}_adj.csv")
    if os.path.exists(p):
        return pd.read_csv(p, parse_dates=["t"], index_col="t")["adj"]
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?period1={P1}&period2={P2}&interval=1d&includeAdjustedClose=true")
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]
            adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose")
            if adj is None: adj = r["indicators"]["quote"][0]["close"]
            rows = [(dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), a)
                    for t, a in zip(ts, adj) if a is not None]
            s = pd.DataFrame(rows, columns=["t", "adj"])
            s["t"] = pd.to_datetime(s["t"]); s = s.set_index("t").sort_index()
            s = s[~s.index.duplicated(keep="last")]
            s.to_csv(p)
            return s["adj"]
        except Exception as e:
            last = e; time.sleep(2 ** k)
    raise last

# ---- 統計(本体と同一定義だが再記述=コードパス分離) ----
def perm_p_m(s, n=3000, seed=13):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    ms = s.groupby(s.index.to_period("M")).sum().values
    rng = np.random.default_rng(seed); real = ms.sum(); a = np.abs(ms)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)]) >= real).mean())

def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net=0.0, dd=0.0, n=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net=round((eq.iloc[-1]-1)*100,1), dd=round(dd,1), n=int(len(x)))

# ---- V1: N5 独立再実装(ベクトル化, close→close) ----
def n5_vec(closes_map, ratio=0.95, lb=252, bps=BASE_BPS, minp=200):
    """closes_map: name->daily close Series。返り値: 月次系列(ON銘柄の等加重・コスト控除)"""
    per = {}
    for a, c in closes_map.items():
        hi = c.rolling(lb, min_periods=minp).max()
        near = (c / hi) >= ratio
        m_near = near.groupby(near.index.to_period("M")).last()
        m_close = c.groupby(c.index.to_period("M")).last()
        nxt = m_close.pct_change().shift(-1)
        on = m_near & nxt.notna()
        per[a] = (nxt - bps/1e4).where(on)
    M = pd.concat(per, axis=1)
    s = M.mean(axis=1, skipna=True).dropna()
    s.index = s.index.to_timestamp("M")
    return s, M

def n5_vec_o2o(opens_map, closes_map, ratio=0.95, lb=252, bps=BASE_BPS):
    """open→open 変形(EA同形): 前月末closeで判定→当月初open建て→翌月初open決済。"""
    per = {}
    for a in opens_map:
        c, o = closes_map[a], opens_map[a]
        hi = c.rolling(lb, min_periods=200).max()
        near = ((c / hi) >= ratio).groupby(c.index.to_period("M")).last()
        mo = o.groupby(o.index.to_period("M")).first()       # 月初open
        nxt = (mo.shift(-2) / mo.shift(-1) - 1.0)            # 判定月+1の月初→+2の月初
        per[a] = (nxt - bps/1e4).where(near & nxt.notna())
    M = pd.concat(per, axis=1)
    s = M.mean(axis=1, skipna=True).dropna()
    s.index = s.index.to_timestamp("M")
    return s

# ---- V1b: N2 独立再実装(ベクトル化) ----
def n2_vec(tnx, usdjpy, delay=0):
    w_t = tnx.resample("W-FRI").last().dropna()
    w_j = usdjpy.resample("W-FRI").last().dropna()
    sig = np.sign(w_t.diff()).shift(delay)
    nxt = w_j.pct_change().shift(-1)
    cost = 2.0*0.01/w_j
    df = pd.concat([sig.rename("s"), nxt.rename("r"), cost.rename("c")], axis=1).dropna()
    df = df[df["s"] != 0]
    return (df["s"]*df["r"] - df["c"]).rename("pnl")

def jackknife_years(s):
    yrs = sorted(set(s.index.year))
    return {int(y): round(perm_p_m(s[s.index.year != y]), 3) for y in yrs}

def run():
    out = {}
    closes = {a: load(a)["close"] for a in IDX}
    opens = {a: load(a)["open"] for a in IDX}

    # ---- V1: 独立再実装 vs 本体 ----
    import importlib.util
    spec = importlib.util.spec_from_file_location("edge10", os.path.join(HERE, "edge10_newaxes_10y.py"))
    e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)
    orig = e10.n5_nearhigh52().dropna()
    vec, perM = n5_vec(closes)
    j = pd.concat([orig.rename("o"), vec.rename("v")], axis=1).dropna()
    maxdiff = float((j["o"]-j["v"]).abs().max())
    st_o, st_v = stats(orig), stats(vec)
    out["V1_n5_reimpl"] = dict(maxdiff=round(maxdiff, 10), orig=st_o, vec=st_v,
                               match=bool(maxdiff < 1e-9 and st_o["n"] == st_v["n"]))
    print(f"V1 N5再実装: 月次系列 最大絶対差={maxdiff:.2e} n(orig)={st_o['n']} n(vec)={st_v['n']} "
          f"net {st_o['net']} vs {st_v['net']} → 一致={out['V1_n5_reimpl']['match']}")

    orig2 = e10.n2_rates2jpy().dropna()
    vec2 = n2_vec(load("TNX")["close"], load("USDJPY")["close"])
    j2 = pd.concat([orig2.rename("o"), vec2.rename("v")], axis=1).dropna()
    md2 = float((j2["o"]-j2["v"]).abs().max())
    out["V1_n2_reimpl"] = dict(maxdiff=round(md2, 10), orig=stats(orig2), vec=stats(vec2),
                               match=bool(md2 < 1e-9 and len(orig2) == len(vec2)))
    print(f"V1 N2再実装: 最大絶対差={md2:.2e} n {len(orig2)} vs {len(vec2)} → 一致={out['V1_n2_reimpl']['match']}")

    # ---- V2: 取引定義 o2o(EA同形) ----
    o2o = n5_vec_o2o(opens, closes)
    out["V2_n5_o2o"] = dict(**stats(o2o), perm_p=round(perm_p_m(o2o), 4))
    print(f"V2 N5 open→open(EA同形): net {out['V2_n5_o2o']['net']}% dd {out['V2_n5_o2o']['dd']}% "
          f"n={out['V2_n5_o2o']['n']} p={out['V2_n5_o2o']['perm_p']}")

    # ---- V3: 感応度格子 ----
    grid = {}
    for ratio in (0.90, 0.925, 0.95, 0.975):
        for lb in (200, 252, 300):
            s, _ = n5_vec(closes, ratio=ratio, lb=lb)
            grid[f"r{ratio}_lb{lb}"] = dict(**stats(s), perm_p=round(perm_p_m(s), 4))
    out["V3_grid"] = grid
    pos = sum(1 for v in grid.values() if v["net"] > 0)
    sig = sum(1 for v in grid.values() if v["perm_p"] <= 0.0083)
    print(f"V3 感応度格子(12点): net>0 {pos}/12 | Bonferroni通過 {sig}/12")
    for k, v in grid.items(): print(f"   {k:14s} net {v['net']:7.1f}% dd {v['dd']:6.1f}% p {v['perm_p']}")

    # ---- V4: 銘柄分解 ----
    per_asset = {}
    for a in IDX:
        s, _ = n5_vec({a: closes[a]})
        per_asset[a] = dict(**stats(s), perm_p=round(perm_p_m(s), 4))
        print(f"V4 {a}: net {per_asset[a]['net']}% dd {per_asset[a]['dd']}% p {per_asset[a]['perm_p']}")
    out["V4_per_asset"] = per_asset

    # ---- V5: シード安定性 ----
    ps = [perm_p_m(vec, seed=s) for s in range(1, 21)]
    out["V5_seed"] = dict(min=round(min(ps),4), max=round(max(ps),4),
                          med=round(float(np.median(ps)),4),
                          all_bonf=bool(max(ps) <= 0.0083))
    print(f"V5 シード20本: p min {min(ps):.4f} med {np.median(ps):.4f} max {max(ps):.4f} "
          f"全点Bonferroni通過={out['V5_seed']['all_bonf']}")
    jk = jackknife_years(vec)
    out["V5_jk"] = jk
    print(f"V5 JK(再実装): max {max(jk.values())}")

    # ---- V6: 配当込みETF ----
    etf_c = {n: fetch_etf(n, s) for n, s in ETF.items()}
    s_etf, _ = n5_vec(etf_c)
    bh = pd.concat([c.groupby(c.index.to_period('M')).last().pct_change() for c in etf_c.values()],
                   axis=1).mean(axis=1).dropna() - BASE_BPS/1e4
    bh.index = bh.index.to_timestamp("M")
    out["V6_etf_adj"] = dict(**stats(s_etf), perm_p=round(perm_p_m(s_etf), 4),
                             jk_max=max(jackknife_years(s_etf).values()),
                             buyhold=stats(bh))
    v6 = out["V6_etf_adj"]
    print(f"V6 配当込みETF(SPY/QQQ/EWG): net {v6['net']}% dd {v6['dd']}% n={v6['n']} p={v6['perm_p']} "
          f"JKmax={v6['jk_max']} | B&H net {v6['buyhold']['net']}% dd {v6['buyhold']['dd']}%")

    # ---- V7: 銘柄別タイミングプラセボ(厳格版) ----
    rng = np.random.default_rng(7)
    draws = 500
    nxt_map, on_cnt = {}, {}
    for a in IDX:
        m = closes[a].groupby(closes[a].index.to_period("M")).last()
        nxt_map[a] = (m.pct_change().shift(-1) - BASE_BPS/1e4).dropna()
        on_cnt[a] = int(perM[a].notna().sum())
    nets, dds = [], []
    for _ in range(draws):
        cols = {}
        for a in IDX:
            v = nxt_map[a]
            pick = rng.choice(len(v), size=on_cnt[a], replace=False)
            x = pd.Series(np.nan, index=v.index); x.iloc[pick] = v.iloc[pick]
            cols[a] = x
        s = pd.concat(cols, axis=1).mean(axis=1, skipna=True).dropna()
        st = stats(s); nets.append(st["net"]); dds.append(st["dd"])
    nets, dds = np.array(nets), np.array(dds)
    cn, cd = stats(vec)["net"], stats(vec)["dd"]
    out["V7_per_asset_timing_placebo"] = dict(
        on=dict(on_cnt), net_pctile=round(float((nets < cn).mean()*100),1),
        dd_pctile=round(float((dds < cd).mean()*100),1),
        tp_net_med=round(float(np.median(nets)),1), tp_dd_med=round(float(np.median(dds)),1))
    v7 = out["V7_per_asset_timing_placebo"]
    print(f"V7 銘柄別タイミングプラセボ: 候補 net pct={v7['net_pctile']} (ランダム中央{v7['tp_net_med']}%) "
          f"| dd pct={v7['dd_pctile']} (ランダム中央{v7['tp_dd_med']}%)")

    # ---- N2 副検証: 実行遅延1週 + シード ----
    d1 = n2_vec(load("TNX")["close"], load("USDJPY")["close"], delay=1)
    ps2 = [perm_p_m(vec2, seed=s) for s in range(1, 21)]
    out["V8_n2"] = dict(delay1=dict(**stats(d1), perm_p=round(perm_p_m(d1), 4)),
                        seed_min=round(min(ps2),4), seed_max=round(max(ps2),4))
    print(f"V8 N2: 1週遅延 net {out['V8_n2']['delay1']['net']}% p {out['V8_n2']['delay1']['perm_p']} "
          f"| シードp範囲 [{min(ps2):.4f},{max(ps2):.4f}]")

    with open(os.path.join(HERE, "results", "verify_edge10_n5.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存: research/results/verify_edge10_n5.json")
    return out

if __name__ == "__main__":
    run()
