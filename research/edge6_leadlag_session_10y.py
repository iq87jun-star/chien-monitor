"""
edge6_leadlag_session_10y.py — 3本目・4本目エッジの事前登録ハーネス（10年実データ・頑健版）

目的:
  v7（円・月曜シーズナリティ）と【独立な】3本目・4本目エッジを、edge5 と同一の
  厳格6ゲートで探索する。FX内のカレンダー/順方向/平均回帰/モメンタムは docs/14,17,
  20,21,22,23 で全滅済みのため、ここでは【未踏の2土俵】だけを事前登録する:

    ■ 土俵A = クロスアセット・リード/ラグ（安全資産・リスク資産がFXを先行する仮説）
        LL1_GOLD_LEADS_JPY   : 金(XAUUSD)の前週リターン符号 → 翌週 円クロスを SHORT
                               （金↑=リスクオフ=円高=円クロス↓ を狙う。週次・1週保有）
        LL2_EQ_LEADS_RISKFX  : 米株(US500)の前週リターン符号 → 翌週 リスクFXバスケット
                               （LONG AUDUSD/NZDJPY・SHORT USDCHF。週次・1週保有）
        LL3_GOLD_LEADS_JPY_D : LL1の日次ラグ版（金の前日符号 → 翌日 円クロス SHORT）

    ■ 土俵B = セッション・ブレイクアウト（東京/欧州レンジの突破が継続する仮説）
        SB1_ASIA_BREAK_EU    : アジア時間(00-06UTC)の終値レンジを欧州開始(07)が突破した
                               方向に建て、欧州終了(16)で決済。FX8バスケット。
        SB2_LONDON_OPEN_RANGE: ロンドン始動レンジ(07-09)を10時終値が突破→20時決済。
        SB3_NY_BREAK_OVNIGHT : NY始動レンジ(13-15)を16時終値が突破→翌日08時決済(オーバー
                               ナイト継続)。

事前登録（PRE-REGISTRATION・当てるまで増やさない）:
  - 候補数 N = 6（固定）。Bonferroni α = 0.05 / 6 ≒ 0.0083。
  - 検定は【10年実データ】のみ（FX H1=dukascopy / 多資産日足=Yahoo）。
  - 全6ゲート通過のみ ADOPT。1つも通らなければ「3本目なし」と正直に結論する。

★ edge5 との差分（意図的・docs/25 の規律に忠実化）:
  edge5 のコードは ADOPT 判定に cost ゲートを含めていなかった。本ハーネスは
  「全主要ゲート通過のみ ADOPT」の規律どおり cost も ADOPT 必須にする（6/6 要求）。

6ゲート（edge5 と同一エンジン）:
  G_perm  : 順列p(月次ブロック符号シャッフル=自己相関頑健版) <= Bonferroni α
  G_jk    : ジャックナイフ(各年除外)最大p <= 0.10
  G_oos   : 前半IS純益>0 かつ 後半OOS純益>0
  G_indep : v7との10年月次相関 |corr| <= 0.4（低/負相関=分散先）
  G_plac  : プラセボ(方向ランダム化)が非有意(p>0.05) かつ 対象の純益>プラセボ純益
  G_cost  : 往復コストを 1→4pip までスイープしても全て純益>0

データの置き場（Colab=Drive / ローカル=フォールバック。edge5 と同一規約）:
  - FX H1   : DRIVE_BASE/dukascopy_data_h1/<PAIR>_h1.csv  （無ければ ./research/data/）
  - 多資産日足: DRIVE_BASE/multiasset_daily/<NAME>_d.csv   （無ければ ./research/data/）
  ※ 多資産日足が未取得なら edge5 の「データ取得セル」(fetch_multiasset) を先に実行。

⚠ シミュレーション。日足終値モデル/週次・セッション・スプレッド近似。LEAD は検証済みエッジ
   ではない。本資金即投入は禁止。ADOPT が出ても縮小サイズ＋デモ前進検証が前提（docs/25）。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# ============================ 設定 ============================
USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"
RESULT_NAME = "edge6_leadlag_session_10y.json"

BASE_BPS        = 5.0          # 非FX脚(本ハーネスでは未使用)の基準コスト
ROUND_TRIP_PIPS = 2.0          # FX往復コスト(基準2pip)。cost ゲートで 1..4 をスイープ。
COST_PIPS_SWEEP = (1.0, 2.0, 3.0, 4.0)

# FX(相関用にH1終値、JPYクロスのpipは0.01)
FX_ALL = ["EURJPY","GBPJPY","USDJPY","EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD","EURGBP","NZDJPY"]
JPY    = ["EURJPY","GBPJPY","USDJPY"]
FX8_BREAKOUT  = ["EURUSD","GBPUSD","USDJPY","EURJPY","GBPJPY","AUDUSD","USDCHF","NZDJPY"]
JPY_SHORT_LEGS = [("EURJPY",-1),("GBPJPY",-1),("USDJPY",-1)]          # 円高で利益=円クロスSHORT
RISK_FX_LEGS   = [("AUDUSD",+1),("NZDJPY",+1),("USDCHF",-1)]          # リスクオンで利益
CRYPTO = ["BTCUSD","ETHUSD"]   # is_fx 判定の都合で定義(本ハーネスでは日足扱い)

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル?):", e); USE_DRIVE = False

# ============================ データ層（edge5と同一） ============================
def is_fx(a):  return a in FX_ALL
def pip(p):    return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(name, daily=False):
    c = []
    if USE_DRIVE:
        if daily:
            b = DAILY_DIR.format(base=DRIVE_BASE); c += [f"{b}/{name}_d.csv", f"{b}/{name}.csv"]
        else:
            b = H1_DIR.format(base=DRIVE_BASE);    c += [f"{b}/{name}_h1.csv", f"{b}/{name}.csv"]
    c += [f"{LOCAL_FALLBACK}/{name}_d.csv"] if daily else [f"{LOCAL_FALLBACK}/{name}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None

def _read_close(path):
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc = next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE = {}
def series(name):
    """FXはH1終値、多資産は日足終値を返す(無ければNone)。"""
    if name not in CACHE:
        p = _resolve(name, daily=not is_fx(name))
        CACHE[name] = _read_close(p) if p else None
    return CACHE[name]
def have(a):  return series(a) is not None
def avail(xs): return [a for a in xs if have(a)]

def daily_close(name):
    s = series(name)
    if s is None: return None
    return s.resample("1D").last().dropna() if is_fx(name) else s

def weekly_close(name):
    d = daily_close(name)
    if d is None: return None
    return d.resample("W-FRI").last().dropna()

# ============================ シグナル（新規6本） ============================
def _legs(rows):
    """(timestamp, ret) のリスト → 同一timestampを平均(=その時点のポートフォリオ)、時系列化。"""
    if not rows: return pd.Series(dtype=float)
    s = pd.Series([v for _, v in rows], index=[t for t, _ in rows])
    return s.groupby(s.index).mean().sort_index()

def _leg_cost(asset, price, rt_pips):
    """FX脚の往復コストをリターン換算(=rt_pips*pip/price)。非FXはbps。"""
    if is_fx(asset): return rt_pips * pip(asset) / price
    return pd.Series(BASE_BPS * (2.0 if asset in CRYPTO else 1.0) / 1e4, index=price.index)

def leadlag(leader, legs, freq="W", randomize=False, seed=1, rt_pips=ROUND_TRIP_PIPS):
    """leader の前期リターン符号で legs バスケットを翌期 建てる。freq='W'(週次)/'D'(日次)。
       legs = [(asset, weight)]. weight 符号でLONG/SHORT。シグナルはshift(1)でラグ確保(先読み無し)。"""
    rng = np.random.default_rng(seed)
    lead = weekly_close(leader) if freq == "W" else daily_close(leader)
    if lead is None or len(lead) < 12: return pd.Series(dtype=float)
    sig = np.sign(lead.pct_change()).shift(1)
    if randomize:
        sig = pd.Series(rng.choice([-1.0, 1.0], size=len(lead.index)), index=lead.index)
    parts, costs = [], []
    for a, w in legs:
        wc = weekly_close(a) if freq == "W" else daily_close(a)
        if wc is None: continue
        parts.append((wc.pct_change() * w).rename(a))
        costs.append(_leg_cost(a, wc, rt_pips).rename(a))
    if not parts: return pd.Series(dtype=float)
    basket = pd.concat(parts, axis=1).mean(axis=1)
    cost   = pd.concat(costs, axis=1).mean(axis=1)
    df = pd.concat([sig.rename("s"), basket.rename("b"), cost.rename("c")], axis=1).dropna()
    return (df["s"] * df["b"] - df["c"]).dropna()

def session_breakout(range_hours, decide_hour, hold_hours, fx_list,
                     randomize=False, seed=3, rt_pips=ROUND_TRIP_PIPS):
    """セッション終値レンジ突破。range_hours(UTC)の終値でhi/lo→decide_hour終値が突破した
       方向に建て、decide_hour+hold_hours の終値で決済(オーバーナイト可)。FXバスケット。"""
    rng = np.random.default_rng(seed); rh = list(range_hours); rows = []
    for a in fx_list:
        s = series(a)
        if s is None: continue
        m = {ts: float(v) for ts, v in s.items()}      # timestamp→close 直引き(先読み無し)
        days = pd.DatetimeIndex(s.index.normalize().unique())
        for d in days:
            try:
                rc = [m[d + pd.Timedelta(hours=h)] for h in rh]   # レンジ終値が全て存在する日のみ
            except KeyError:
                continue
            t_in  = d + pd.Timedelta(hours=decide_hour)
            t_out = t_in + pd.Timedelta(hours=hold_hours)
            cd = m.get(t_in); ce = m.get(t_out)
            if cd is None or ce is None: continue
            hi, lo = max(rc), min(rc)
            dirn = 1 if cd > hi else (-1 if cd < lo else 0)
            if dirn == 0: continue
            if randomize: dirn = int(rng.choice([-1, 1]))
            rows.append((t_in, dirn * (ce / cd - 1.0) - rt_pips * pip(a) / cd))
    return _legs(rows)

# 事前登録(N=6 固定)。cost スイープのため rt_pips を引数化。
CAND = {
 "LL1_GOLD_LEADS_JPY"    : lambda rt=ROUND_TRIP_PIPS: leadlag("XAUUSD", JPY_SHORT_LEGS, freq="W", rt_pips=rt),
 "LL2_EQ_LEADS_RISKFX"   : lambda rt=ROUND_TRIP_PIPS: leadlag("US500",  RISK_FX_LEGS,   freq="W", rt_pips=rt),
 "LL3_GOLD_LEADS_JPY_D"  : lambda rt=ROUND_TRIP_PIPS: leadlag("XAUUSD", JPY_SHORT_LEGS, freq="D", rt_pips=rt),
 "SB1_ASIA_BREAK_EU"     : lambda rt=ROUND_TRIP_PIPS: session_breakout(range(0,7),  7, 9,  FX8_BREAKOUT, rt_pips=rt),
 "SB2_LONDON_OPEN_RANGE" : lambda rt=ROUND_TRIP_PIPS: session_breakout([7,8,9],    10, 10, FX8_BREAKOUT, rt_pips=rt),
 "SB3_NY_BREAK_OVNIGHT"  : lambda rt=ROUND_TRIP_PIPS: session_breakout([13,14,15], 16, 16, FX8_BREAKOUT, rt_pips=rt),
}
PLAC = {
 "LL1_GOLD_LEADS_JPY"    : lambda: leadlag("XAUUSD", JPY_SHORT_LEGS, freq="W", randomize=True),
 "LL2_EQ_LEADS_RISKFX"   : lambda: leadlag("US500",  RISK_FX_LEGS,   freq="W", randomize=True),
 "LL3_GOLD_LEADS_JPY_D"  : lambda: leadlag("XAUUSD", JPY_SHORT_LEGS, freq="D", randomize=True),
 "SB1_ASIA_BREAK_EU"     : lambda: session_breakout(range(0,7),  7, 9,  FX8_BREAKOUT, randomize=True),
 "SB2_LONDON_OPEN_RANGE" : lambda: session_breakout([7,8,9],    10, 10, FX8_BREAKOUT, randomize=True),
 "SB3_NY_BREAK_OVNIGHT"  : lambda: session_breakout([13,14,15], 16, 16, FX8_BREAKOUT, randomize=True),
}

# ============================ 統計・ゲート（edge5と同一エンジン） ============================
def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n)]) >= real).mean())

def perm_p_robust(s, n=3000, seed=13):
    """月次集約してから符号シャッフル=自己相関頑健の保守的p(docs/25)。"""
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    ms = s.groupby(s.index.to_period("M")).sum()
    return perm_p(ms.values, n=n, seed=seed)

def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

def jackknife(s):
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None
    jk = {int(y): round(perm_p_robust(s[s.index.year != y]), 3) for y in yrs}  # 各年除外で頑健p
    return jk, round(max(jk.values()), 3)

def mP(s):
    return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

def yen_monday_monthly():
    """v7(円・月曜04/06/08/10UTC LONG・24h)の月次リターンをFX H1から再現→相関ゲート用。"""
    rows = []
    for p in JPY:
        if not have(p): continue
        s = series(p); cv = s.values; idx = s.index; ps = pip(p)
        for hr in (4, 6, 8, 10):
            a = np.where((idx.dayofweek == 0) & (idx.hour == hr))[0]; a = a[a + 24 < len(cv)]
            for i in a:
                rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i] - 2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s = pd.Series([r for _, r in rows], index=[d for d, _ in rows])
    return s.groupby(s.index.to_period("M")).sum()

# ============================ 実行 ============================
def run():
    print("利用可能 FX:", avail(FX_ALL))
    print("利用可能 多資産:", avail(["XAUUSD","US500","NAS100","GER40","BTCUSD","ETHUSD"]))
    N = len(CAND); bonf = round(0.05 / N, 4); ym = yen_monday_monthly()
    out = {"meta": dict(n_candidates=N, bonferroni_alpha=bonf, round_trip_pips=ROUND_TRIP_PIPS,
                        cost_pips_sweep=list(COST_PIPS_SWEEP), v7_corr_months=len(ym),
                        adopt_rule="6/6 (perm,jk,oos,indep,placebo,cost)"),
           "candidates": {}}
    print(f"\n試行数 N={N} Bonferroni α={bonf} / v7基準月数={len(ym)}\n")

    for name, fn in CAND.items():
        s = fn()
        if len(s) < 30:
            out["candidates"][name] = dict(note="insufficient", n=len(s))
            print(f"\n{name}: データ不足 n={len(s)}"); continue
        st = stats(s)
        p_daily = round(perm_p(s.values), 4)                 # 参考(非頑健)
        p       = round(perm_p_robust(s), 4)                 # ★gateは頑健版p
        jk = jackknife(s); jkmax = jk[1] if jk else None
        h = s.index[len(s)//2]; isr, oos = s[s.index < h], s[s.index >= h]
        j = pd.concat([mP(s).rename("c"), ym.rename("y")], axis=1).dropna()
        corr = round(float(j["c"].corr(j["y"])), 2) if len(j) > 12 else None
        plc = PLAC[name](); plc_p = round(perm_p_robust(plc), 3); plc_net = stats(plc)["net_pct"]
        cost = {f"{c}pip": stats(fn(c))["net_pct"] for c in COST_PIPS_SWEEP}
        dd_ok = st["maxDD_pct"] >= -10.0

        g_perm  = p <= bonf
        g_jk    = (jkmax is not None and jkmax <= 0.10)
        g_oos   = (stats(isr)["net_pct"] > 0 and stats(oos)["net_pct"] > 0)
        g_indep = (corr is None) or abs(corr) <= 0.4
        g_plac  = (plc_p > 0.05 and st["net_pct"] > plc_net)
        g_cost  = all(v > 0 for v in cost.values())
        gates = dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost)
        passed = sum(gates.values())
        grade = "ADOPT" if all(gates.values()) else ("LEAD" if (st["net_pct"] > 0 and p <= 0.10) else "REJECT")

        out["candidates"][name] = dict(**st, perm_p=p, perm_p_daily=p_daily, jackknife_max_p=jkmax,
            IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"], corr_to_v7=corr,
            placebo_net=plc_net, placebo_p=plc_p, cost=cost, dd_within_10pct=dd_ok,
            gates=gates, gates_passed=f"{passed}/6", grade=grade)
        ddn = "" if dd_ok else f"  ⚠DD{st['maxDD_pct']}%<-10%(縮小サイズ/衛星前提)"
        print(f"\n### {name}  [{grade}] {passed}/6{ddn}")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | "
              f"p頑健={p}(日次{p_daily}/Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | "
              f"placebo純{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")

    adopts = [n for n, r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads  = [n for n, r in out["candidates"].items() if r.get("grade") == "LEAD"]
    out["adopted"], out["leads"] = adopts, leads
    print("\n>>> 10年ADOPT:", adopts or "なし")
    print(">>> LEAD(要追検):", leads or "なし")
    if not adopts and not leads:
        print(">>> 全滅 → 3本目・4本目なし。v7単独で確定(誠実な結論)。")
    elif adopts:
        print(">>> ADOPT候補あり → 縮小サイズでDD/合格率を実測+デモ前進検証(本資金は確認後)。")

    try:
        path = (DAILY_DIR.format(base=DRIVE_BASE) + "/" + RESULT_NAME) if USE_DRIVE else ("research/results/" + RESULT_NAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f: json.dump(out, f, ensure_ascii=False, indent=2, default=str)
        print("保存:", path)
    except Exception as e:
        print("保存スキップ:", e)
    return out

if __name__ == "__main__":
    run()
