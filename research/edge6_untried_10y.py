"""
edge6_untried_10y.py — 3本目・4本目エッジの【自走・一括事前登録】10年検定。
ユーザーの意向を待たずに、docs/26 の「未踏の土俵」から6候補を事前登録して同条件で検定する。

経緯: v7(円月曜LONG)が唯一の検証済み。FX内のカレンダー/順方向/平均回帰/モメンタムは全滅
(docs/14,17,20,21,22)。多資産トレンドはLEAD止まり(docs/23)。本バッチは"まだ打っていない構造"
=①ボラ・レジーム条件付け ②クロスアセットのリード・ラグ ③多資産の平均回帰 ④リスクパリティ加重
⑤相対強さローテーション、を10年日足で検定する。

データ: ./research/data の日足10年(2016-2026, FX=Yahoo日足化, 多資産=Yahoo日足)。
        v7相関は H1(2023-2026, 2.76年)から円月曜月次を再現して算出(重複月で相関)。
⚠ 日足/月次終値モデル・スワップ/品質スプレッド/配当調整は未精緻。LEAD以上は足内+デモで要追検。

事前登録6候補(N=6, Bonferroni α=0.05/6=0.0083):
  E1 VOLREGIME_TREND : 金+株価指数のTSMOMを、バスケット実現ボラが低レジーム(24mローリング中央値以下)
                       のときだけON(高ボラ=トレンド崩れでOFF)。条件付けは未トライ。
  E2 LEADLAG_EQ2JPY  : 株(US500)の前月リターン符号 → 翌月の円3クロスLONG/見送り(risk-onで円安/キャリー)。
                       USD先行(docs/15)は弱だったが"株→円"の先行は未トライ。
  E3 LEADLAG_GOLD2CHF: 金の前月リターン符号 → 翌月USDCHFを逆張り方向(金高=CHF高=USDCHF安)。安全資産連動。
  E4 MULTIASSET_MR   : 金+株価指数の月次zスコア(3m)逆張り(z>+1.5→翌月SHORT / z<-1.5→翌月LONG)。
                       平均回帰はFXのみ検定済(docs/21)=多資産MRは未トライ。
  E5 RP_TREND        : 金+株価指数のTSMOMを各レッグ逆ボラ加重(リスクパリティ)。DD低減狙い(等加重はMA2)。
  E6 RS_ROTATION     : 毎月、金/US500/NAS100/GER40/BTC の6mモメンタム最強1本だけをLONG保有(ロング限定回転)。
  PLC 各候補に整合プラセボ=同機会・ランダム方向(方向シグナルが無価値かの帰無)。

ゲート(全て10年・採用は全主要通過): G_perm 頑健p<=Bonf / G_jk JKmax<=0.10 / G_oos IS・OOS両+ /
  G_indep v7月次相関<=0.4(負が望) / G_plac プラセボ非有意かつ候補>プラセボ / G_cost 2-20bpsで+
ADOPT=主要ゲート全通過。LEAD=net>0かつ頑健p<=0.10。1つも無ければ3本目なし(誠実な結論)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

LOCAL = "./research/data"
BASE_BPS = 5.0
LOOKBACKS = [1, 3, 6, 12]
MR_LB = 3
MR_Z = 1.5

YEN        = ["EURJPY", "GBPJPY", "USDJPY"]
METALS_IDX = ["XAUUSD", "US500", "NAS100", "GER40"]
ROT        = ["XAUUSD", "US500", "NAS100", "GER40", "BTCUSD"]
CRYPTO     = ["BTCUSD", "ETHUSD"]

def is_fx(a): return a in YEN or a.endswith("USD") and a in ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD"] or a in ["USDCHF"]
def _isfx(a): return a in (YEN + ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD"])
def pip(p): return 0.01 if p.endswith("JPY") else 0.0001

def _read_close(path):
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc = next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE = {}
def series(name, daily=True):
    key = (name, daily)
    if key not in CACHE:
        p = f"{LOCAL}/{name}_d.csv" if daily else f"{LOCAL}/{name}_h1.csv"
        CACHE[key] = _read_close(p) if os.path.exists(p) else None
    return CACHE[key]
def have(a): return series(a) is not None
def avail(assets): return [a for a in assets if have(a)]

def daily_close(name): return series(name, daily=True)
def monthly_close(name):
    d = daily_close(name)
    if d is None: return None
    m = d.groupby(d.index.to_period("M")).last(); m.index = m.index.to_timestamp("M"); return m

def cost_m(a):  # 月次の往復コスト(価格分数)
    if _isfx(a): return None
    return BASE_BPS * (2.0 if a in CRYPTO else 1.0) / 1e4

# ---------- 統計ハーネス(edge5と同一) ----------
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

def yen_monday_monthly():
    rows = []
    for p in YEN:
        s = series(p, daily=False)
        if s is None: continue
        cv = s.values; idx = s.index; ps = pip(p)
        for hr in (4,6,8,10):
            a = np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a = a[a+24 < len(cv)]
            for i in a: rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s = pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

# ---------- 候補シグナル(randomize=整合プラセボ) ----------
def _series_from(legs):
    if not legs: return pd.Series(dtype=float)
    s = pd.Series([v for _,v in legs], index=[t for t,_ in legs])
    return s.groupby(s.index).mean().sort_index()

def basket_monthly_ret(assets):
    cols = {a: monthly_close(a).pct_change() for a in avail(assets) if monthly_close(a) is not None}
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def e1_volregime_trend(randomize=False, seed=1, bps=BASE_BPS):
    """金+指数TSMOM、バスケット実現ボラが低レジームのときだけON。"""
    rng = np.random.default_rng(seed)
    br = basket_monthly_ret(METALS_IDX)
    vol = br.rolling(6).std(); med = vol.rolling(24, min_periods=12).median()
    low = (vol <= med)  # 低ボラ=ON
    legs = []
    for a in avail(METALS_IDX):
        m = monthly_close(a)
        if m is None or len(m) < max(LOOKBACKS)+3: continue
        comp = sum(np.sign(m.pct_change(L)) for L in LOOKBACKS); pos = np.sign(comp)
        nxt = m.pct_change().shift(-1); c = bps*(2.0 if a in CRYPTO else 1.0)/1e4
        for t in m.index[:-1]:
            if not bool(low.get(t, False)): continue
            p0 = pos.get(t, 0)
            if not np.isfinite(p0) or p0 == 0: continue
            d = rng.choice([-1,1]) if randomize else p0
            legs.append((t, d*nxt[t]-c))
    return _series_from(legs)

def _leadlag(leader, traded, sign, randomize, seed, longonly=False):
    rng = np.random.default_rng(seed)
    lm = monthly_close(leader)
    if lm is None: return pd.Series(dtype=float)
    lead_sig = np.sign(lm.pct_change())  # 前月の先行資産リターン符号
    legs = []
    for a in (traded if isinstance(traded, list) else [traded]):
        m = monthly_close(a)
        if m is None: continue
        nxt = m.pct_change().shift(-1)
        cpr = (2.0*pip(a)/m) if _isfx(a) else pd.Series(cost_m(a), index=m.index)
        for t in m.index[:-1]:
            sg = lead_sig.get(t, 0)
            if not np.isfinite(sg) or sg == 0: continue
            d = sign*sg
            if longonly and d < 0: continue   # ロング限定なら逆方向は見送り
            d = rng.choice([-1,1]) if randomize else d
            if randomize and longonly and d < 0: continue
            legs.append((t, d*nxt[t]-cpr[t]))
    return _series_from(legs)

def e2_leadlag_eq2jpy(randomize=False, seed=2, bps=None):
    # 株(US500)上昇→翌月 円クロスLONG(risk-on=円安/キャリー)。ロング限定(プロップ親和)。
    return _leadlag("US500", YEN, +1, randomize, seed, longonly=True)

def e3_leadlag_gold2chf(randomize=False, seed=3, bps=None):
    # 金上昇→CHF高→USDCHF安(SHORT)。sign=-1。
    return _leadlag("XAUUSD", "USDCHF", -1, randomize, seed, longonly=False)

def e4_multiasset_mr(randomize=False, seed=4, bps=BASE_BPS):
    rng = np.random.default_rng(seed); legs = []
    for a in avail(METALS_IDX):
        m = monthly_close(a)
        if m is None or len(m) < MR_LB+3: continue
        r = m.pct_change()
        z = (r - r.rolling(12, min_periods=6).mean()) / r.rolling(12, min_periods=6).std()
        nxt = r.shift(-1); c = bps*(2.0 if a in CRYPTO else 1.0)/1e4
        for t in m.index[:-1]:
            zz = z.get(t, np.nan)
            if not np.isfinite(zz) or abs(zz) < MR_Z: continue
            d = -np.sign(zz)  # 逆張り
            d = rng.choice([-1,1]) if randomize else d
            legs.append((t, d*nxt[t]-c))
    return _series_from(legs)

def e5_rp_trend(randomize=False, seed=5, bps=BASE_BPS):
    """金+指数TSMOMを逆ボラ加重(リスクパリティ)。月次pnlを加重平均。"""
    rng = np.random.default_rng(seed)
    rets, sigs, ws = {}, {}, {}
    for a in avail(METALS_IDX):
        m = monthly_close(a)
        if m is None or len(m) < max(LOOKBACKS)+3: continue
        comp = sum(np.sign(m.pct_change(L)) for L in LOOKBACKS); pos = np.sign(comp)
        r = m.pct_change(); c = bps*(2.0 if a in CRYPTO else 1.0)/1e4
        invvol = 1.0 / r.rolling(12, min_periods=6).std()
        rets[a] = r.shift(-1); sigs[a] = pos; ws[a] = invvol
        rets[a].name = a
    if not rets: return pd.Series(dtype=float)
    idx = sorted(set().union(*[set(s.index) for s in sigs.values()]))
    out = {}
    for t in idx:
        num, den = 0.0, 0.0
        for a in rets:
            p0 = sigs[a].get(t, 0); w = ws[a].get(t, np.nan); nx = rets[a].get(t, np.nan)
            if not (np.isfinite(p0) and p0 != 0 and np.isfinite(w) and np.isfinite(nx)): continue
            d = rng.choice([-1,1]) if randomize else p0
            num += w * (d*nx - BASE_BPS/1e4); den += w
        if den > 0: out[t] = num/den
    return pd.Series(out).sort_index().dropna()

def e6_rs_rotation(randomize=False, seed=6, bps=BASE_BPS):
    """毎月6mモメンタム最強1本だけLONG(ロング限定回転)。"""
    rng = np.random.default_rng(seed)
    M = pd.concat({a: monthly_close(a) for a in avail(ROT) if monthly_close(a) is not None}, axis=1).dropna(how="all")
    if M.shape[1] < 2: return pd.Series(dtype=float)
    mom = M.pct_change(6); nxt = M.pct_change().shift(-1)
    out = {}
    for t in M.index[:-1]:
        mm = mom.loc[t].dropna()
        if len(mm) < 2: continue
        if randomize:
            pick = rng.choice(list(mm.index))
        else:
            if mm.max() <= 0: continue   # ロング限定: 全て下落ならキャッシュ
            pick = mm.idxmax()
        nx = nxt.loc[t].get(pick, np.nan)
        if not np.isfinite(nx): continue
        c = bps*(2.0 if pick in CRYPTO else 1.0)/1e4
        out[t] = nx - c
    return pd.Series(out).sort_index().dropna()

CAND = {
 "E1_VOLREGIME_TREND":  lambda b=BASE_BPS: e1_volregime_trend(bps=b),
 "E2_LEADLAG_EQ2JPY":   lambda b=BASE_BPS: e2_leadlag_eq2jpy(),
 "E3_LEADLAG_GOLD2CHF": lambda b=BASE_BPS: e3_leadlag_gold2chf(),
 "E4_MULTIASSET_MR":    lambda b=BASE_BPS: e4_multiasset_mr(bps=b),
 "E5_RP_TREND":         lambda b=BASE_BPS: e5_rp_trend(bps=b),
 "E6_RS_ROTATION":      lambda b=BASE_BPS: e6_rs_rotation(bps=b),
}
PLAC = {
 "E1_VOLREGIME_TREND":  lambda: e1_volregime_trend(randomize=True),
 "E2_LEADLAG_EQ2JPY":   lambda: e2_leadlag_eq2jpy(randomize=True),
 "E3_LEADLAG_GOLD2CHF": lambda: e3_leadlag_gold2chf(randomize=True),
 "E4_MULTIASSET_MR":    lambda: e4_multiasset_mr(randomize=True),
 "E5_RP_TREND":         lambda: e5_rp_trend(randomize=True),
 "E6_RS_ROTATION":      lambda: e6_rs_rotation(randomize=True),
}

def run():
    N = len(CAND); bonf = round(0.05/N, 4); ym = yen_monday_monthly()
    print("利用可能:", avail(METALS_IDX + ROT + YEN), "| v7基準月数:", len(ym))
    print(f"試行数N={N} Bonferroniα={bonf} / コスト基準{BASE_BPS}bps")
    out = {"meta": dict(n=N, bonferroni_alpha=bonf, lookbacks=LOOKBACKS), "candidates": {}}
    for name, fn in CAND.items():
        s = fn()
        if len(s) < 24:
            out["candidates"][name] = dict(note="insufficient", n=len(s))
            print(f"\n{name}: データ不足 n={len(s)}"); continue
        st = stats(s); p_daily = round(perm_p(s.values), 4); p = round(perm_p_robust(s), 4)
        jk = jackknife(s); jkmax = jk[1] if jk else None
        h = s.index[len(s)//2]; isr, oos = s[s.index < h], s[s.index >= h]
        j = pd.concat([mP(s).rename("c"), ym.rename("y")], axis=1).dropna()
        corr = round(float(j["c"].corr(j["y"])), 2) if len(j) > 12 else None
        plc = PLAC[name](); plc_p = round(perm_p_robust(plc), 3); plc_net = stats(plc)["net_pct"]
        cost = {f"{c}bps": stats(fn(float(c)))["net_pct"] for c in (2,5,10,20)}
        dd_ok = st["maxDD_pct"] >= -10.0
        g_perm = p <= bonf; g_jk = (jkmax is not None and jkmax <= 0.10)
        g_oos = (isr.sum() > 0 and oos.sum() > 0); g_indep = (corr is None) or abs(corr) <= 0.4
        g_plac = (plc_p > 0.05 and st["net_pct"] > plc_net); g_cost = all(v > 0 for v in cost.values())
        passed = sum([g_perm, g_jk, g_oos, g_indep, g_plac, g_cost])
        grade = "ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac) else ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")
        out["candidates"][name] = dict(**st, perm_p=p, perm_p_daily=p_daily, jackknife_max_p=jkmax,
            IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"], corr_to_v7=corr,
            placebo_net=plc_net, placebo_p=plc_p, cost=cost, dd_within_10pct=dd_ok,
            gates=dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost),
            gates_passed=f"{passed}/6", grade=grade)
        dn = "" if dd_ok else f" ⚠DD{st['maxDD_pct']}%≫-10%=素サイズ不可(要縮小+デモ)"
        print(f"\n### {name}  [{grade}] {passed}/6{dn}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p頑健={p}(日次{p_daily}/Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts = [n for n,r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads = [n for n,r in out["candidates"].items() if r.get("grade") == "LEAD"]
    print("\n>>> 10年ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 未踏6候補も全滅 → 3本目なし、v7一本で確定(誠実な結論)。")
    out["adopted"] = adopts; out["leads"] = leads
    os.makedirs("research/results", exist_ok=True)
    with open("research/results/edge6_untried_10y.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("保存: research/results/edge6_untried_10y.json")
    return out

if __name__ == "__main__":
    run()
