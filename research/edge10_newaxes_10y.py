"""
edge10_newaxes_10y.py — 新エッジ自走探索バッチ第2弾【未踏6軸・一括事前登録】10年検定。

経緯: docs/27(edge6)で多資産トレンド/MR/リードラグ系は尽きた(本命E5=LEAD止まり)。
docs/64(hejzum)でカレンダー軸(祝前日/年末年始/月別)も検定済(S-Jul=SEASONAL-LEADのみ)。
docs/64-67(hsjec9)でレジームゲート(実現ボラ/SMA)も検定済(RG3=DD保険として採用)。
本バッチは docs/26 が列挙しながら一度も実行されなかった軸＋リポジトリ全文grepで未踏を確認した軸:
  ①ボラ・リスクプレミアム(VIX期間構造) ②金利→円リードラグ ③FXクロスセクショナルL/S
  ④銅/金比リスク選好リード ⑤52週高値近接(George-Hwang) ⑥VIXスパイク後リバウンド
を Yahoo日足10年(固定窓2016-2026, docs/71の再現性規約準拠)で検定する。

データ: Yahoo日足を固定窓(period1=1451606400, period2=1767225599)で自動取得し
        research/data/<NAME>_yd.csv にキャッシュ。⚠ 指数=配当除く・FX=Yahoo指標値・
        終値モデル＝一次近似。確証は Drive(Dukascopy/実CFD)+デモ前進検証(docs/19系譜)。

事前登録6候補(N=6, Bonferroni α=0.05/6=0.0083):
  N1 VIXTS_INDEX   : VIX期間構造(VIX3M−VIX>0=コンタンゴ)の週だけ翌週 指数バスケットLONG。
                     ボラ・リスクプレミアムの定番。ゲートでなく方向シグナルとしては未踏。
  N2 RATES2JPY     : 米10年金利(^TNX)の週次変化符号 → 翌週USDJPYを同方向(金利↑=円安)。
                     docs/26「金利→円の先行性」を初実行。
  N3 FXXS_MOM      : 毎月、G6通貨(EUR/GBP/AUD/CHF/CAD/JPY)の対USD 3mモメンタムで
                     最強通貨LONG×最弱通貨SHORT(クロスセクショナルL/S)。FXのTSモメンタムは
                     全滅済(docs/20)だが横断L/Sは未踏(E6はロング限定・暗号込み回転で別物)。
  N4 COPPERGOLD    : 銅/金比の3mモメンタム>0(リスク選好)の月だけ翌月 指数バスケットLONG。
                     Dr.Copperリードは未踏。
  N5 NEARHIGH_52W  : 終値が52週高値の95%以上の指数だけ翌月LONG(George-Hwang 1990s)。
                     SMAトレンド(E1/MA2)とは別シグナル族で未踏。
  N6 VIXSPIKE_MR   : 週次VIXが13週中央値の1.5倍超(スパイク)の翌週 指数バスケットLONG。
                     ボラ平均回帰=危機リバウンド。E4(価格zスコアMR)とは条件変数が別。
  PLC 各候補に整合プラセボ=同機会・ランダム方向。

ゲート(edge6と同一): G_perm 頑健p<=Bonf / G_jk JKmax<=0.10 / G_oos IS・OOS両+ /
  G_indep 既存エッジ(E-Mon・v7日次proxy)との月次|相関|<=0.4 / G_plac プラセボ非有意かつ候補>プラセボ /
  G_cost 2-20bpsで全+。 ADOPT=perm/jk/oos/indep/plac全通過。LEAD=net>0かつ頑健p<=0.10。
規律: 数字は盛らない。出なければ「出ない」と書く。
"""
import os, json, csv, time, datetime as dt
import urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

BASE_BPS = 5.0
# 固定窓で凍結(docs/71): 2016-01-01..2025-12-31
P1, P2 = 1451606400, 1767225599

YAHOO = {
    "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "XAUUSD": "GC=F",
    "VIX": "^VIX", "VIX3M": "^VIX3M", "TNX": "^TNX", "COPPER": "HG=F",
    "USDJPY": "USDJPY=X", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
}
IDX_BASKET = ["US500", "NAS100"]
EMON_BASKET = ["NAS100", "US500", "GER40"]
YEN = ["EURJPY", "GBPJPY", "USDJPY"]
G6 = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "USDJPY"]


def _fetch(name, tries=6):
    p = os.path.join(DATA, f"{name}_yd.csv")
    if os.path.exists(p):
        df = pd.read_csv(p, parse_dates=["t"], index_col="t")
        return df
    sym = YAHOO[name]
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?period1={P1}&period2={P2}&interval=1d")
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            rows = [(dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), q["open"][i], q["close"][i])
                    for i, t in enumerate(ts) if q["open"][i] is not None and q["close"][i] is not None]
            df = pd.DataFrame(rows, columns=["t", "open", "close"])
            df["t"] = pd.to_datetime(df["t"]); df = df.set_index("t").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            df.to_csv(p)
            return df
        except Exception as e:
            last = e; time.sleep(2 ** k)
    raise last


CACHE = {}
def D(name):
    if name not in CACHE:
        CACHE[name] = _fetch(name)
        time.sleep(1.0)
    return CACHE[name]

def closes(name): return D(name)["close"]
def weekly(name): return closes(name).resample("W-FRI").last().dropna()
def monthly(name):
    m = closes(name).groupby(closes(name).index.to_period("M")).last()
    m.index = m.index.to_timestamp("M"); return m

def fx_cost(name, px):  # 往復2pip(価格分数)
    pip = 0.01 if name.endswith("JPY") else 0.0001
    return 2.0 * pip / px

# ---------- 統計ハーネス(edge6と同一) ----------
def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)]) >= real).mean())
def perm_p_robust(s, n=3000, seed=13):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    ms = s.groupby(s.index.to_period("M")).sum()
    return perm_p(ms.values, n=n, seed=seed)
def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1+x).cumprod(); dd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))
def jackknife(s):
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    jk = {int(y): round(perm_p_robust(s[s.index.year != y]),3) for y in yrs}
    return jk, round(max(jk.values()),3)
def mP(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

# ---------- 既存エッジの月次proxy(独立性ゲート基準) ----------
def emon_monthly():
    legs = []
    for a in EMON_BASKET:
        df = D(a); o = df["open"]
        mon = np.where(o.index.dayofweek == 0)[0]
        mon = mon[mon + 1 < len(o)]
        for i in mon:
            legs.append((o.index[i], (o.iloc[i+1] - o.iloc[i]) / o.iloc[i] - BASE_BPS/1e4))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return mP(s.groupby(s.index).mean().sort_index())

def v7proxy_monthly():
    legs = []
    for a in YEN:
        df = D(a); o = df["open"]
        mon = np.where(o.index.dayofweek == 0)[0]
        mon = mon[mon + 1 < len(o)]
        for i in mon:
            legs.append((o.index[i], (o.iloc[i+1] - o.iloc[i]) / o.iloc[i] - fx_cost(a, o.iloc[i])))
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return mP(s.groupby(s.index).mean().sort_index())

# ---------- 候補(randomize=整合プラセボ) ----------
def _basket_weekly_ret(assets):
    cols = {a: weekly(a).pct_change() for a in assets}
    return pd.concat(cols, axis=1).mean(axis=1)

def _basket_monthly_ret(assets):
    cols = {a: monthly(a).pct_change() for a in assets}
    return pd.concat(cols, axis=1).mean(axis=1)

def n1_vixts(randomize=False, seed=1, bps=BASE_BPS):
    rng = np.random.default_rng(seed)
    ts = (weekly("VIX3M") - weekly("VIX")).dropna()
    nxt = _basket_weekly_ret(IDX_BASKET).shift(-1)
    out = {}
    for t in ts.index[:-1]:
        if not (np.isfinite(ts[t]) and ts[t] > 0): continue
        nx = nxt.get(t, np.nan)
        if not np.isfinite(nx): continue
        d = rng.choice([-1, 1]) if randomize else 1
        out[t] = d * nx - bps/1e4
    return pd.Series(out).sort_index()

def n2_rates2jpy(randomize=False, seed=2, bps=None):
    rng = np.random.default_rng(seed)
    dt_ = weekly("TNX").diff()
    w = weekly("USDJPY"); nxt = w.pct_change().shift(-1)
    out = {}
    for t in dt_.index[:-1]:
        sg = np.sign(dt_.get(t, np.nan))
        if not np.isfinite(sg) or sg == 0: continue
        nx = nxt.get(t, np.nan)
        if not np.isfinite(nx): continue
        d = rng.choice([-1, 1]) if randomize else sg
        px = w.get(t, np.nan)
        out[t] = d * nx - (fx_cost("USDJPY", px) if np.isfinite(px) else 0.0)
    return pd.Series(out).sort_index()

def n3_fxxs_mom(randomize=False, seed=3, bps=None):
    rng = np.random.default_rng(seed)
    # 対USDの「外貨リターン」: XXXUSD=そのまま / USDXXX=逆数
    cur = {}
    for p in G6:
        m = monthly(p)
        cur[p[:3] if p.startswith(("EUR","GBP","AUD")) else p[3:]] = (m if p.startswith(("EUR","GBP","AUD")) else 1.0/m)
    M = pd.concat(cur, axis=1).dropna(how="all")
    mom = M.pct_change(3); nxt = M.pct_change().shift(-1)
    out = {}
    for t in M.index[:-1]:
        mm = mom.loc[t].dropna()
        if len(mm) < 4: continue
        hi, lo = mm.idxmax(), mm.idxmin()
        if hi == lo: continue
        if randomize:
            hi, lo = rng.choice(list(mm.index), size=2, replace=False)
        r_hi, r_lo = nxt.loc[t].get(hi, np.nan), nxt.loc[t].get(lo, np.nan)
        if not (np.isfinite(r_hi) and np.isfinite(r_lo)): continue
        out[t] = 0.5*(r_hi - r_lo) - 2.0*1e-4  # 2レッグ往復≈2pip相当
    return pd.Series(out).sort_index()

def n4_coppergold(randomize=False, seed=4, bps=BASE_BPS):
    rng = np.random.default_rng(seed)
    ratio = (monthly("COPPER") / monthly("XAUUSD")).dropna()
    mom = ratio.pct_change(3)
    nxt = _basket_monthly_ret(IDX_BASKET).shift(-1)
    out = {}
    for t in mom.index[:-1]:
        if not (np.isfinite(mom[t]) and mom[t] > 0): continue
        nx = nxt.get(t, np.nan)
        if not np.isfinite(nx): continue
        d = rng.choice([-1, 1]) if randomize else 1
        out[t] = d * nx - bps/1e4
    return pd.Series(out).sort_index()

def n5_nearhigh52(randomize=False, seed=5, bps=BASE_BPS):
    rng = np.random.default_rng(seed)
    legs = []
    for a in IDX_BASKET + ["GER40"]:
        c = closes(a); hi = c.rolling(252, min_periods=200).max()
        near = (c / hi) >= 0.95
        m_near = near.groupby(near.index.to_period("M")).last()
        m_near.index = m_near.index.to_timestamp("M")
        nxt = monthly(a).pct_change().shift(-1)
        for t in m_near.index[:-1]:
            if not bool(m_near.get(t, False)): continue
            nx = nxt.get(t, np.nan)
            if not np.isfinite(nx): continue
            d = rng.choice([-1, 1]) if randomize else 1
            legs.append((t, d * nx - bps/1e4))
    if not legs: return pd.Series(dtype=float)
    s = pd.Series([v for _, v in legs], index=[t for t, _ in legs])
    return s.groupby(s.index).mean().sort_index()

def n6_vixspike(randomize=False, seed=6, bps=BASE_BPS):
    rng = np.random.default_rng(seed)
    v = weekly("VIX"); med = v.rolling(13, min_periods=8).median()
    spike = v > 1.5 * med
    nxt = _basket_weekly_ret(IDX_BASKET).shift(-1)
    out = {}
    for t in spike.index[:-1]:
        if not bool(spike.get(t, False)): continue
        nx = nxt.get(t, np.nan)
        if not np.isfinite(nx): continue
        d = rng.choice([-1, 1]) if randomize else 1
        out[t] = d * nx - bps/1e4
    return pd.Series(out).sort_index()

CAND = {
 "N1_VIXTS_INDEX": n1_vixts, "N2_RATES2JPY": n2_rates2jpy, "N3_FXXS_MOM": n3_fxxs_mom,
 "N4_COPPERGOLD": n4_coppergold, "N5_NEARHIGH_52W": n5_nearhigh52, "N6_VIXSPIKE_MR": n6_vixspike,
}

# ロング限定・指数系候補のドリフト識別(E6の教訓: ランダム方向プラセボは強気相場ベータを殺せない)
# → 同数のランダム期間にロングする「タイミング・プラセボ」分布に対する候補のパーセンタイルを採点。
LONGONLY_UNIVERSE = {
    "N1_VIXTS_INDEX": ("W", IDX_BASKET),
    "N4_COPPERGOLD": ("M", IDX_BASKET),
    "N5_NEARHIGH_52W": ("M", IDX_BASKET + ["GER40"]),
    "N6_VIXSPIKE_MR": ("W", IDX_BASKET),
}

def timing_placebo(name, cand, draws=500, seed=99, bps=BASE_BPS):
    if name not in LONGONLY_UNIVERSE: return None
    freq, basket = LONGONLY_UNIVERSE[name]
    nxt = (_basket_weekly_ret(basket) if freq == "W" else _basket_monthly_ret(basket)).shift(-1).dropna()
    k = len(cand)
    if k == 0 or k > len(nxt): return None
    rng = np.random.default_rng(seed)
    nets, dds = [], []
    vals = nxt.values - bps/1e4
    for _ in range(draws):
        pick = np.sort(rng.choice(len(vals), size=k, replace=False))
        r = vals[pick]
        eq = np.cumprod(1+r)
        nets.append((eq[-1]-1)*100)
        dds.append(((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min()*100)
    nets, dds = np.array(nets), np.array(dds)
    cn, cd = stats(cand)["net_pct"], stats(cand)["maxDD_pct"]
    bh = stats(nxt - bps/1e4)["net_pct"]
    return dict(buyhold_net=bh, k=k, universe_n=len(nxt),
                tp_net_med=round(float(np.median(nets)),1), tp_net_p95=round(float(np.percentile(nets,95)),1),
                net_pctile=round(float((nets < cn).mean()*100),1),
                tp_dd_med=round(float(np.median(dds)),1),
                dd_pctile=round(float((dds < cd).mean()*100),1))  # DDは「候補より深い割合」=高いほど候補のDDが浅い

def run():
    N = len(CAND); bonf = round(0.05/N, 4)
    em, v7 = emon_monthly(), v7proxy_monthly()
    print(f"試行数N={N} Bonferroniα={bonf} / コスト基準{BASE_BPS}bps / E-Mon月数{len(em)} v7proxy月数{len(v7)}")
    out = {"meta": dict(n=N, bonferroni_alpha=bonf, window="2016-01-01..2025-12-31 (frozen)"),
           "candidates": {}}
    for name, fn in CAND.items():
        s = fn().dropna()
        if len(s) < 24:
            out["candidates"][name] = dict(note="insufficient", n=len(s))
            print(f"\n{name}: データ不足 n={len(s)}"); continue
        st = stats(s); p = round(perm_p_robust(s), 4)
        jk = jackknife(s); jkmax = jk[1] if jk else None
        h = s.index[len(s)//2]; isr, oos = s[s.index < h], s[s.index >= h]
        cm = mP(s)
        j_em = pd.concat([cm.rename("c"), em.rename("e")], axis=1).dropna()
        j_v7 = pd.concat([cm.rename("c"), v7.rename("v")], axis=1).dropna()
        c_em = round(float(j_em["c"].corr(j_em["e"])), 2) if len(j_em) > 12 else None
        c_v7 = round(float(j_v7["c"].corr(j_v7["v"])), 2) if len(j_v7) > 12 else None
        plc = fn(randomize=True).dropna()
        plc_p = round(perm_p_robust(plc), 3); plc_net = stats(plc)["net_pct"]
        cost = {f"{c}bps": stats(fn(bps=float(c)).dropna())["net_pct"] for c in (2,5,10,20)} \
               if name not in ("N2_RATES2JPY", "N3_FXXS_MOM") else \
               {f"x{m}": stats((fn().dropna()) - (m-1)*2e-4)["net_pct"] for m in (1,2,3)}
        g_perm = p <= bonf; g_jk = (jkmax is not None and jkmax <= 0.10)
        g_oos = (isr.sum() > 0 and oos.sum() > 0)
        g_indep = all(c is None or abs(c) <= 0.4 for c in (c_em, c_v7))
        g_plac = (plc_p > 0.05 and st["net_pct"] > plc_net)
        g_cost = all(v > 0 for v in cost.values())
        tp = timing_placebo(name, s)
        # ベータ識別: ロング限定指数系は「ランダム同数ロング」分布に対し純益かDDのどちらかでp95超を要求
        g_beta = (tp is None) or (tp["net_pctile"] >= 95.0 or tp["dd_pctile"] >= 95.0)
        passed = sum([g_perm, g_jk, g_oos, g_indep, g_plac, g_cost])
        grade = "ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac and g_beta) else \
                ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")
        out["candidates"][name] = dict(**st, perm_p=p, jackknife_max_p=jkmax,
            IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"],
            corr_to_emon=c_em, corr_to_v7proxy=c_v7,
            placebo_net=plc_net, placebo_p=plc_p, cost=cost, timing_placebo=tp,
            gates=dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost, beta=g_beta),
            gates_passed=f"{passed}/6", grade=grade)
        print(f"\n### {name}  [{grade}] {passed}/6 beta_ok={g_beta}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p頑健={p}(Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | corr E-Mon{c_em}/v7 {c_v7}({g_indep}) | placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
        if tp: print(f"   タイミングプラセボ: B&H{tp['buyhold_net']}% ON {tp['k']}/{tp['universe_n']} | ランダム同数L 純中央{tp['tp_net_med']}%/p95 {tp['tp_net_p95']}% → 候補純pct={tp['net_pctile']} | DD中央{tp['tp_dd_med']}% → 候補DDpct={tp['dd_pctile']}")
    adopts = [n for n,r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads = [n for n,r in out["candidates"].items() if r.get("grade") == "LEAD"]
    print("\n>>> ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    out["adopted"] = adopts; out["leads"] = leads
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "edge10_newaxes_10y.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存: research/results/edge10_newaxes_10y.json")
    return out

if __name__ == "__main__":
    run()
