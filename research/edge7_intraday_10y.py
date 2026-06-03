"""
edge7_intraday_10y.py — 4本目エッジの【自走・一括事前登録】10年検定（H1足内・別構造）。

経緯: v7(円月曜LONG・24h保有)が唯一の検証済み。多資産トレンド/MR/リードラグ系はLEAD止まり
(docs/23,27)。本バッチは"足内(H1)の別構造"=セッション・ブレイクアウト/フェード/初動継続/
オーバーナイトを検定する。v7とは時間軸・建て方が構造的に別=分散先になりうる。

★データ: 10年 H1。【拘束力ある検定はユーザーのGoogle Drive実行】(dukascopy_data_h1, 実bid/ask)。
   ローカルは2.76年(2023-2026)しか無いので、ローカル実行は"スモーク(動作確認)"であり結論ではない。
   USE_DRIVE=True で Drive を優先し、無ければローカルにフォールバックする。

事前登録6候補(N=6, Bonferroni α=0.05/6=0.0083) — 全てUTC・1日1ペア1トレード・時間決済:
  I1 LONDON_ORB   : アジア時間帯(00-07)の高安レンジを、ロンドン(07-11)にブレイクした方向に建て16時決済。
  I2 NY_ORB       : ロンドン時間帯(07-12)レンジを、NY(12-15)にブレイクした方向に建て20時決済。
  I3 LONDON_FADE  : I1の逆=ブレイク方向の反対(ダマシ取り・足内平均回帰)。16時決済。
  I4 FIRSTHOUR_CONT: ロンドン初動(07-08)の方向に08時建て→16時決済(初動継続=モメンタム)。
  I5 OVERNIGHT    : 21時建て→翌06時決済。方向=前日リターン符号(オーバーナイト継続)。全曜日。
  I6 TOKYO_BREAK_JPY: 円3クロス、アジアレンジ(00-06)を東京→ロンドン(06-09)にブレイク、14時決済。
  PLC 各候補に整合プラセボ=同機会・ランダム方向(方向シグナルが無価値かの帰無)。

ゲート(全て10年・採用は全主要通過): G_perm 頑健p<=Bonf / G_jk JKmax<=0.10 / G_oos IS・OOS両+ /
  G_indep v7月次相関<=0.4(負が望) / G_plac プラセボ非有意かつ候補>プラセボ / G_cost 2-20bpsで+
ADOPT=主要ゲート全通過。LEAD=net>0かつ頑健p<=0.10。1つも無ければ4本目なし(誠実な結論)。

⚠ H1足内モデル。SLは各候補のレンジ反対側を災害ストップに置く近似。スワップ/品質スプレッド/
   約定すべりは未精緻。LEAD以上は足内エンジン精査＋デモ前進検証を経ること。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

YEN    = ["EURJPY", "GBPJPY", "USDJPY"]
MAJORS = ["EURUSD", "GBPUSD", "USDJPY"]    # ORB/継続系の主対象(流動性高)
RTRIP_PIP = 2.0                            # 往復コスト(pip)。実運用はデモで確認

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")
print(f"[データ] Drive={DRIVE_OK} 探索基点 {H1_DIR.format(base=DRIVE_BASE)} / fallback {LOCAL_FALLBACK}")

def pip(p): return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(pair):
    c = [f"{H1_DIR.format(base=DRIVE_BASE)}/{pair}_h1.csv",
         f"{H1_DIR.format(base=DRIVE_BASE)}/{pair}.csv",
         f"{LOCAL_FALLBACK}/{pair}_h1.csv", f"{LOCAL_FALLBACK}/{pair}.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None

def _load(pair):
    path = _resolve(pair)
    if path is None: return None
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pk(*n):
        for x in n:
            if x in df.columns: return x
        return None
    o,h,l,c = pk("open","bidopen","o"), pk("high","bidhigh","h"), pk("low","bidlow","l"), pk("close","bidclose","c")
    out = pd.DataFrame(index=df.index)
    out["open"]=df[o].astype(float); out["high"]=df[h].astype(float)
    out["low"]=df[l].astype(float);  out["close"]=df[c].astype(float)
    return out.dropna()

CACHE = {}
def H1(p):
    if p not in CACHE: CACHE[p] = _load(p)
    return CACHE[p]
def have(p): return H1(p) is not None

# ---------- 統計ハーネス(edge5/6と同一) ----------
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
        s = H1(p)
        if s is None: continue
        cv = s["close"].values; idx = s.index; ps = pip(p)
        for hr in (4,6,8,10):
            a = np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a = a[a+24 < len(cv)]
            for i in a: rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s = pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

# ---------- 足内トレード生成 ----------
def _day_groups(df):
    return df.groupby(df.index.normalize())

def orb(pairs, asia_win, bo_win, exit_hr, fade=False, randomize=False, seed=1, rtrip=RTRIP_PIP):
    """レンジ・ブレイクアウト/フェード。asia_win=(s,e) レンジ時間帯, bo_win=(s,e) ブレイク監視帯。"""
    rng = np.random.default_rng(seed); out = []
    for pair in pairs:
        df = H1(pair)
        if df is None: continue
        ps = pip(pair); cost = rtrip*ps
        for day, g in _day_groups(df):
            hh = g.index.hour
            r = g[(hh >= asia_win[0]) & (hh < asia_win[1])]
            if len(r) < 2: continue
            hi, lo = r["high"].max(), r["low"].min()
            bo = g[(hh >= bo_win[0]) & (hh < bo_win[1])]
            ex = g[hh == exit_hr]
            if len(bo) == 0 or len(ex) == 0: continue
            entry = None; direction = 0
            for t, row in bo.iterrows():
                if row["close"] > hi: direction = 1; entry = row["close"]; break
                if row["close"] < lo: direction = -1; entry = row["close"]; break
            if entry is None or direction == 0: continue
            if fade: direction = -direction
            if randomize: direction = rng.choice([-1, 1])
            exitpx = ex["close"].iloc[0]
            ret = direction * (exitpx - entry) / entry - cost / entry
            out.append((bo.index[0], ret))
    if not out: return pd.Series(dtype=float)
    s = pd.Series([r for _,r in out], index=[t for t,_ in out])
    return s.groupby(s.index).mean().sort_index()

def firsthour_cont(pairs, sig_hr, entry_hr, exit_hr, randomize=False, seed=4, rtrip=RTRIP_PIP):
    """初動継続: sig_hr 足の方向に entry_hr で建て exit_hr 決済。"""
    rng = np.random.default_rng(seed); out = []
    for pair in pairs:
        df = H1(pair)
        if df is None: continue
        ps = pip(pair); cost = rtrip*ps
        for day, g in _day_groups(df):
            hh = g.index.hour
            sig = g[hh == sig_hr]; ent = g[hh == entry_hr]; ex = g[hh == exit_hr]
            if len(sig)==0 or len(ent)==0 or len(ex)==0: continue
            d = np.sign(sig["close"].iloc[0] - sig["open"].iloc[0])
            if d == 0: continue
            if randomize: d = rng.choice([-1, 1])
            e = ent["close"].iloc[0]; xpx = ex["close"].iloc[0]
            out.append((ent.index[0], d*(xpx-e)/e - cost/e))
    if not out: return pd.Series(dtype=float)
    s = pd.Series([r for _,r in out], index=[t for t,_ in out])
    return s.groupby(s.index).mean().sort_index()

def overnight(pairs, entry_hr, exit_hr, randomize=False, seed=5, rtrip=RTRIP_PIP):
    """オーバーナイト継続: entry_hr建て→翌exit_hr決済。方向=前日(同時刻比)リターン符号。"""
    rng = np.random.default_rng(seed); out = []
    for pair in pairs:
        df = H1(pair)
        if df is None: continue
        ps = pip(pair); cost = rtrip*ps
        ent = df[df.index.hour == entry_hr]["close"]
        ex  = df[df.index.hour == exit_hr]["close"]
        if len(ent) < 3 or len(ex) < 3: continue
        ent_by_day = {t.normalize(): v for t, v in ent.items()}
        ex_by_day  = {t.normalize(): v for t, v in ex.items()}
        days = sorted(ent_by_day.keys())
        prev_ret = ent.pct_change()
        prev_by_day = {t.normalize(): v for t, v in prev_ret.items()}
        for i in range(1, len(days)):
            day = days[i]; nxt = day + pd.Timedelta(days=1)
            if nxt not in ex_by_day:
                # exit翌日が無ければ当日内のexitを試す
                if day not in ex_by_day: continue
                xpx = ex_by_day[day]
            else:
                xpx = ex_by_day[nxt]
            e = ent_by_day[day]; d = np.sign(prev_by_day.get(day, 0))
            if d == 0: continue
            if randomize: d = rng.choice([-1, 1])
            out.append((day, d*(xpx-e)/e - cost/e))
    if not out: return pd.Series(dtype=float)
    s = pd.Series([r for _,r in out], index=[t for t,_ in out])
    return s.groupby(s.index).mean().sort_index()

CAND = {
 "I1_LONDON_ORB":    lambda r=RTRIP_PIP: orb(MAJORS, (0,7),  (7,11),  16, rtrip=r),
 "I2_NY_ORB":        lambda r=RTRIP_PIP: orb(MAJORS, (7,12), (12,15), 20, rtrip=r),
 "I3_LONDON_FADE":   lambda r=RTRIP_PIP: orb(MAJORS, (0,7),  (7,11),  16, fade=True, rtrip=r),
 "I4_FIRSTHOUR_CONT":lambda r=RTRIP_PIP: firsthour_cont(MAJORS, 7, 8, 16, rtrip=r),
 "I5_OVERNIGHT":     lambda r=RTRIP_PIP: overnight(MAJORS, 21, 6, rtrip=r),
 "I6_TOKYO_BREAK_JPY":lambda r=RTRIP_PIP: orb(YEN, (0,6), (6,9), 14, rtrip=r),
}
PLAC = {
 "I1_LONDON_ORB":    lambda: orb(MAJORS, (0,7),  (7,11),  16, randomize=True),
 "I2_NY_ORB":        lambda: orb(MAJORS, (7,12), (12,15), 20, randomize=True),
 "I3_LONDON_FADE":   lambda: orb(MAJORS, (0,7),  (7,11),  16, fade=True, randomize=True),
 "I4_FIRSTHOUR_CONT":lambda: firsthour_cont(MAJORS, 7, 8, 16, randomize=True),
 "I5_OVERNIGHT":     lambda: overnight(MAJORS, 21, 6, randomize=True),
 "I6_TOKYO_BREAK_JPY":lambda: orb(YEN, (0,6), (6,9), 14, randomize=True),
}

def run():
    span = ""
    for p in MAJORS:
        d = H1(p)
        if d is not None: span = f"{d.index.min().date()}..{d.index.max().date()} ({len(d)}本)"; break
    N = len(CAND); bonf = round(0.05/N, 4); ym = yen_monday_monthly()
    print(f"[期間] {span} | v7基準月数={len(ym)}")
    print(f"試行数N={N} Bonferroniα={bonf} / 往復コスト{RTRIP_PIP}pip")
    if span and "2023" in span:
        print("⚠ ローカル2.76年=スモークのみ。結論はDrive10年で確定すること。")
    out = {"meta": dict(n=N, bonferroni_alpha=bonf, span=span, drive=DRIVE_OK), "candidates": {}}
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
        cost = {f"{c}pip": stats(fn(float(c)))["net_pct"] for c in (1,2,3,4)}
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
        dn = "" if dd_ok else f" ⚠DD{st['maxDD_pct']}%≫-10%=要縮小+デモ"
        print(f"\n### {name}  [{grade}] {passed}/6{dn}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p頑健={p}(日次{p_daily}/Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts = [n for n,r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads = [n for n,r in out["candidates"].items() if r.get("grade") == "LEAD"]
    print("\n>>> 10年ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 足内6候補も全滅 → 4本目なし、v7一本で確定(誠実な結論)。")
    out["adopted"] = adopts; out["leads"] = leads
    try:
        path = (H1_DIR.format(base=DRIVE_BASE)+"/edge7_intraday_10y.json") if DRIVE_OK else "research/results/edge7_intraday_10y.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f: json.dump(out, f, ensure_ascii=False, indent=2, default=str)
        print("保存:", path)
    except Exception as e: print("保存スキップ:", e)
    return out

if __name__ == "__main__":
    run()
