"""
edge_regime_gate_10y.py — 【事前登録ハーネス】RG: 検証済み月曜エッジ(E-Mon/v7)を
ボラ/トレンドのレジームで ON/OFF する"手法"を10年で採点する。docs/64 と対。

目的: 新エッジの発明ではなく、「検証済みエッジの左尾(クラッシュ・ギャップ)を間引いて
合算maxDD・失格率を下げられるか」を、対プラセボ込みで誠実に検定する。
edge6 の E1(弱いトレンドにレジームを足して REJECT)とは土台が違う = 月曜エッジ(ADOPT/STRONG-LEAD)に被せる。

データ: ./research/data の日足10年(2016-2026, FX/指数/金 = *_d.csv)。
        拘束力ある確証はユーザーの Google Drive 実10年で実行(ローカルCSVは短期/一部のみ)。
⚠ 数字は本スクリプトの実行出力のみを docs に転記する。本ファイルに結果はハードコードしない。

事前登録(N=6, Bonferroni α=0.05/6=0.0083):
  RG1 TREND_GATE   : E-Mon月曜L を 各指数 前日Close>SMA200 のときだけ建てる。
  RG2 VOL_GATE     : E-Mon月曜L を バスケット実現ボラ(20d)<=自身80分位 のときだけ建てる。
  RG3 RISKOFF_GATE : SMA200割れ かつ 高ボラ(>80分位) の真リスクオフ週のみ見送り、他は建てる(非対称)。
  RG4 V7_GATE      : v7(円月曜L) に RG3 と同型ゲートを適用。
  RG5 GOLD_HEDGE   : 株価指数が RG3 で OFF の週に XAUUSD を週次LONG(リスクオフ安全資産衛星, long-only)。
  RG6 VOL_TARGET   : ポート週次リスク予算を 直近実現ボラの逆数でスケール(上限あり)。
  PLC 各候補に整合プラセボ: RG1-4=同率ランダム間引き / RG5=ランダム週の金L / RG6=ランダム・リスケール。

ゲート(全て10年・素版との比較が主): G1 span/件数 / G2 ノールック+実コスト / G3 頑健perm_p<Bonf /
  G4 対プラセボ(ゲート版>ランダム) / G5 年次JK<=0.10 / G6 IS-OOS両改善 / G7 コスト2x-20bps /
  G8 -10%枠適合 & 低相関。
ADOPT = ゲート版が素版を OOS で (Calmar かつ p95maxDD) パレート支配 かつ プラセボ超 かつ G3,G5-G8。
LEAD  = net>0 かつ 一部ゲートのみ通過。1つも通らねば「RG 不採用・確定スペック維持」と正直に結論。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "data")
BASE_BPS = 5.0
N_CAND = 6
ALPHA_BONF = 0.05 / N_CAND          # = 0.008333
VOL_WIN = 20                        # 実現ボラ窓(営業日)
VOL_Q = 0.80                        # 高ボラ分位
SMA_WIN = 200                       # トレンド・ゲート窓

YEN     = ["EURJPY", "GBPJPY", "USDJPY"]
EMON    = ["NAS100", "US500", "GER40"]      # docs/50 確定の指数3バスケット
GOLD    = "XAUUSD"
WD_MON  = 0

# Drive(Dukascopy/CFD)が無い環境向けの Yahoo 日足10年フォールバック(=概算・配当除く近似)。
# 拘束力ある確証は Drive 実データ。本フォールバックは docs/50 と同じ"一次近似"の位置づけ。
YAHOO = {"NAS100": "%5EIXIC", "US500": "%5EGSPC", "GER40": "%5EGDAXI", "XAUUSD": "GC=F",
         "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "USDJPY": "USDJPY=X"}


def _yahoo_fetch(name, rng="10y"):
    import urllib.request, time
    sym = YAHOO.get(name)
    if not sym: return None
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?range={rng}&interval=1d")
    for _ in range(3):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            res = d["chart"]["result"][0]
            ts = res["timestamp"]; q = res["indicators"]["quote"][0]
            df = pd.DataFrame({"timestamp": pd.to_datetime(ts, unit="s", utc=True),
                               "open": q["open"], "high": q["high"],
                               "low": q["low"], "close": q["close"]}).dropna()
            os.makedirs(LOCAL, exist_ok=True)
            df.to_csv(os.path.join(LOCAL, f"{name}_d.csv"), index=False)
            return df
        except Exception:
            time.sleep(2)
    return None


# ---------- I/O (parallel_emon_validate.py と同じ規約) ----------
def _read_ohlc(path):
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time", "timestamp", "date", "datetime", "gmt time"]
                 if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    o = next((c for c in ["open", "bidopen", "o"] if c in df.columns), None)
    c = next((c for c in ["close", "bidclose", "c"] if c in df.columns), None)
    out = pd.DataFrame({"open": df[o].astype(float), "close": df[c].astype(float)}).dropna()
    out["o2o"] = out["open"].shift(-1) / out["open"] - 1.0     # open->翌open(時刻順で先に算出)
    # 銘柄間で intraday の時刻が違う(指数13:30 / GER40 07:00 / 金04:00)ため、
    # クロス銘柄の整列はカレンダー日に正規化する(docs/14 の trade_date 正規化と同趣旨)。
    out.index = out.index.floor("D")
    out = out[~out.index.duplicated(keep="first")]
    out["weekday"] = out.index.dayofweek
    out = out[out["weekday"] <= 4].copy()
    return out


CACHE = {}
ALLOW_YAHOO = os.environ.get("RG_ALLOW_YAHOO", "1") == "1"
def load(name):
    if name not in CACHE:
        p = os.path.join(LOCAL, f"{name}_d.csv")
        if os.path.exists(p):
            CACHE[name] = _read_ohlc(p)
        elif ALLOW_YAHOO and _yahoo_fetch(name) is not None:
            CACHE[name] = _read_ohlc(p)
        else:
            CACHE[name] = None
    return CACHE[name]


# ---------- 統計（頑健perm/stat/月次/DD）----------
def stats(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) == 0: return dict(net_pct=0.0, n=0, mean=0.0, sharpe=0.0)
    return dict(net_pct=float(x.sum() * 100), n=int(len(x)),
                mean=float(x.mean()), sharpe=float(x.mean() / (x.std() + 1e-12) * np.sqrt(52)))

def perm_p_block(weekly, n_iter=8000, seed=7):
    """月次ブロック符号シャッフルの自己相関頑健版 perm_p（docs/23 の是正に準拠）。"""
    s = weekly.dropna()
    if len(s) < 20: return 1.0
    m = s.groupby([s.index.year, s.index.month]).sum()       # 月次集約
    obs = m.sum(); rng = np.random.default_rng(seed); cnt = 0
    v = m.values
    for _ in range(n_iter):
        sign = rng.choice([-1.0, 1.0], size=len(v))          # 月次ブロック符号シャッフル
        if abs((v * sign).sum()) >= abs(obs): cnt += 1
    return (cnt + 1) / (n_iter + 1)
    return (cnt + 1) / (n_iter + 1)

def max_dd(weekly):
    eq = (1 + weekly.fillna(0)).cumprod(); return float((eq / eq.cummax() - 1).min())

def calmar(weekly):
    if len(weekly) < 10: return 0.0
    yrs = (weekly.index[-1] - weekly.index[0]).days / 365.25
    cagr = (1 + weekly.fillna(0)).prod() ** (1 / max(yrs, 0.1)) - 1
    dd = abs(max_dd(weekly)); return float(cagr / dd) if dd > 1e-6 else 0.0

def split_is_oos(weekly, frac=0.7):
    n = len(weekly); k = int(n * frac); return weekly.iloc[:k], weekly.iloc[k:]


# ---------- レジーム信号(no-lookahead) ----------
def realized_vol(close, win=VOL_WIN):
    r = np.log(close).diff()
    return (r.rolling(win).std() * np.sqrt(252)).shift(1)      # 前足までで確定

def sma_above(close, win=SMA_WIN):
    return (close > close.rolling(win).mean()).shift(1)        # 前足までで確定

def basket_vol_high(names):
    """E-Monバスケットの実現ボラが自身のローリング80分位超か（週次index, 前足確定）。"""
    vols = []
    for nm in names:
        df = load(nm)
        if df is None: continue
        vols.append(realized_vol(df["close"]).rename(nm))
    if not vols: return None
    bv = pd.concat(vols, axis=1).mean(axis=1).dropna()
    thr = bv.rolling(252, min_periods=60).quantile(VOL_Q)
    return (bv > thr)


# ---------- 月曜バスケット(素 & ゲート) ----------
def emon_weekly_raw(cost_mult=1.0):
    legs = []
    for nm in EMON:
        df = load(nm)
        if df is None: continue
        c = BASE_BPS * 1e-4 * cost_mult
        legs.append((df[df["weekday"] == WD_MON]["o2o"] - c).rename(nm))
    if not legs: return None
    return pd.concat(legs, axis=1).mean(axis=1).dropna()

def basket_regime(names):
    """E-Monバスケット全体の1つのレジーム信号(週次・no-lookahead): 過半が上昇/高ボラ。
    バスケットは1シグナルで建てる(=実運用と同じ)ため、ゲートも週単位で全レッグ一括。"""
    up_parts, hv_high = [], basket_vol_high(names)
    for nm in names:
        df = load(nm)
        if df is None: continue
        up_parts.append(sma_above(df["close"]).rename(nm))
    if not up_parts: return None, None
    up_maj = (pd.concat(up_parts, axis=1).astype(float).mean(axis=1) >= 0.5)   # 過半がSMA上
    return up_maj, hv_high

def emon_weekly_gated(kind, cost_mult=1.0):
    """kind in {trend, vol, riskoff}. バスケット週次レジームで全レッグ一括 ON/OFF。"""
    raw = emon_weekly_raw(cost_mult)
    if raw is None: return None
    up_maj, hv_high = basket_regime(EMON)
    if up_maj is None: return raw
    up = up_maj.reindex(raw.index).fillna(False).astype(bool)
    hv = (hv_high.reindex(raw.index).fillna(False).astype(bool)
          if hv_high is not None else pd.Series(False, index=raw.index))
    if kind == "trend":
        on = up                                   # 上昇局面の週だけ建てる
    elif kind == "vol":
        on = ~hv                                  # 高ボラ週は見送り
    elif kind == "riskoff":
        on = ~((~up) & hv)                        # SMA割れ かつ 高ボラ の真リスクオフ週だけ見送り
    else:
        on = pd.Series(True, index=raw.index)
    return raw.where(on, np.nan).dropna()

def gate_fraction(raw, gated):
    """ゲートが間引いた週の割合（プラセボの間引き率を合わせるため）。"""
    j = pd.concat([raw.rename("r"), gated.rename("g")], axis=1)
    kept = j["g"].notna().sum(); tot = j["r"].notna().sum()
    return 1 - kept / tot if tot else 0.0

def placebo_random_drop(raw, drop_frac, seed=11, reps=200):
    """同率をランダム間引きしたときの (mean net, mean calmar, mean p95dd) の分布中央。"""
    rng = np.random.default_rng(seed); nets, cals, dds = [], [], []
    idx = raw.dropna().index
    for _ in range(reps):
        keep = rng.random(len(idx)) > drop_frac
        s = raw.loc[idx][keep]
        nets.append(stats(s.values)["net_pct"]); cals.append(calmar(s)); dds.append(max_dd(s))
    return dict(net=float(np.median(nets)), calmar=float(np.median(cals)), maxdd=float(np.median(dds)))


# ---------- 採点 ----------
def score_gate(name, raw, gated):
    if raw is None or gated is None:
        return dict(id=name, status="NO_DATA")
    frac = gate_fraction(raw, gated)
    plc = placebo_random_drop(raw, frac)
    raw_is, raw_oos = split_is_oos(raw.dropna())
    g_is, g_oos = split_is_oos(gated.dropna())
    res = dict(
        id=name, kept_frac=round(1 - frac, 3),
        raw=dict(net=round(stats(raw.values)["net_pct"], 2), calmar=round(calmar(raw), 3),
                 maxdd=round(max_dd(raw), 4), sharpe=round(stats(raw.values)["sharpe"], 3)),
        gated=dict(net=round(stats(gated.values)["net_pct"], 2), calmar=round(calmar(gated), 3),
                   maxdd=round(max_dd(gated), 4), sharpe=round(stats(gated.values)["sharpe"], 3),
                   perm_p=round(perm_p_block(gated), 5)),
        placebo=dict(net=round(plc["net"], 2), calmar=round(plc["calmar"], 3), maxdd=round(plc["maxdd"], 4)),
        OOS=dict(raw_calmar=round(calmar(raw_oos), 3), gated_calmar=round(calmar(g_oos), 3),
                 raw_maxdd=round(max_dd(raw_oos), 4), gated_maxdd=round(max_dd(g_oos), 4)),
        alpha_bonf=round(ALPHA_BONF, 6),
    )
    # 判定: OOS で Calmar かつ p95(=maxdd) を素版優越 + プラセボ超 + 頑健p<Bonf
    beats_raw = (res["OOS"]["gated_calmar"] > res["OOS"]["raw_calmar"]
                 and res["OOS"]["gated_maxdd"] > res["OOS"]["raw_maxdd"])
    beats_plc = (res["gated"]["calmar"] > res["placebo"]["calmar"]
                 and res["gated"]["maxdd"] > res["placebo"]["maxdd"])
    sig = res["gated"]["perm_p"] <= ALPHA_BONF
    res["verdict"] = ("ADOPT" if (beats_raw and beats_plc and sig)
                      else "LEAD" if (beats_raw and beats_plc)
                      else "REJECT")
    return res


# ---------- 円バスケットの週次素リターン & レジーム ----------
def v7_weekly_raw(cost_mult=1.0):
    legs = []
    for p in YEN:
        df = load(p)
        if df is None: continue
        c = BASE_BPS * 1e-4 * cost_mult
        legs.append((df[df["weekday"] == WD_MON]["o2o"] - c).rename(p))
    if not legs: return None
    return pd.concat(legs, axis=1).mean(axis=1).dropna()


# ---------- RG4: v7(円月曜LONG)日足プロキシ + リスクオフ・ゲート(バスケット一括) ----------
def v7_weekly_raw_and_gated(cost_mult=1.0):
    raw = v7_weekly_raw(cost_mult)
    if raw is None: return None, None
    up_maj, hv_high = basket_regime(YEN)
    if up_maj is None: return raw, raw
    up = up_maj.reindex(raw.index).fillna(False).astype(bool)
    hv = (hv_high.reindex(raw.index).fillna(False).astype(bool)
          if hv_high is not None else pd.Series(False, index=raw.index))
    on = ~((~up) & hv)                            # 円高(SMA割れ)×高ボラ の真リスクオフ週は見送り
    return raw, raw.where(on, np.nan).dropna()


# ---------- RG5: リスクオフ週だけ建てる金(XAU)ロング衛星(バスケット一括) ----------
def gold_riskoff_weekly(cost_mult=1.0):
    """E-Mon が RG3 で OFF の週(=指数リスクオフ)に XAUUSD を月曜LONG。安全資産ヘッジ衛星。"""
    g = load(GOLD)
    if g is None: return None, None, None
    up_maj, hv_high = basket_regime(EMON)
    if up_maj is None or hv_high is None: return None, None, None
    gmon = g[g["weekday"] == WD_MON].copy()
    c = BASE_BPS * 1e-4 * cost_mult * 0.8        # 金は指数よりやや安い往復近似
    gleg = (gmon["o2o"] - c)
    up = up_maj.reindex(gmon.index).fillna(False).astype(bool)
    hv = hv_high.reindex(gmon.index).fillna(False).astype(bool)
    riskoff = (~up) & hv                          # 指数バスケットが真リスクオフの週
    gold_hedge = gleg.where(riskoff, np.nan).dropna()
    gold_all = gleg.dropna()                       # 比較用: 無条件の金月曜L(=プラセボ)
    return gold_hedge, gold_all, riskoff


def main():
    have_any = os.path.isdir(LOCAL) or ALLOW_YAHOO
    if not have_any:
        print("research/data が無い。Drive/ローカルにFX/指数/金の *_d.csv を置く"
              "(または RG_ALLOW_YAHOO=1 で Yahoo 概算)。")
        return
    out = {}
    raw = emon_weekly_raw()
    if raw is None:
        print("指数データを取得できず(Drive/Yahoo 両方失敗)。"); return
    out["RG1_TREND"]   = score_gate("RG1_TREND",   raw, emon_weekly_gated("trend"))
    out["RG2_VOL"]     = score_gate("RG2_VOL",     raw, emon_weekly_gated("vol"))
    out["RG3_RISKOFF"] = score_gate("RG3_RISKOFF", raw, emon_weekly_gated("riskoff"))

    v7_raw, v7_gate = v7_weekly_raw_and_gated()
    out["RG4_V7"] = (score_gate("RG4_V7", v7_raw, v7_gate) if v7_raw is not None
                     else dict(id="RG4_V7", status="NO_JPY_DATA"))

    gh, ga, _ = gold_riskoff_weekly()
    if gh is not None and len(gh) > 20:
        out["RG5_GOLD"] = dict(
            id="RG5_GOLD", n_riskoff_weeks=int(len(gh)),
            hedge=dict(net=round(stats(gh.values)["net_pct"], 2), sharpe=round(stats(gh.values)["sharpe"], 3),
                       maxdd=round(max_dd(gh), 4), perm_p=round(perm_p_block(gh), 5)),
            gold_all=dict(net=round(stats(ga.values)["net_pct"], 2), sharpe=round(stats(ga.values)["sharpe"], 3),
                          maxdd=round(max_dd(ga), 4)),
            note="hedge=リスクオフ週のみ金L / gold_all=無条件金月曜L(=プラセボ比較). hedge>gold_all & perm<Bonf で衛星価値")
    else:
        out["RG5_GOLD"] = dict(id="RG5_GOLD", status="NO_GOLD_DATA")
    out["RG6_VTGT"] = dict(id="RG6_VTGT", status="PENDING_DRIVE_portfolio_blend")

    print(f"RG 事前登録ハーネス (N={N_CAND}, Bonferroni α={ALPHA_BONF:.4f}) — 素版 vs ゲート版 vs プラセボ")
    print("=" * 78)
    for k, v in out.items():
        if v.get("status"):
            print(f"{k:12s}: {v['status']}"); continue
        if k == "RG5_GOLD":
            h, a = v["hedge"], v["gold_all"]
            print(f"{k:12s}: riskoff週={v['n_riskoff_weeks']}  "
                  f"hedge[net {h['net']:.1f}% sh {h['sharpe']:.2f} dd {h['maxdd']:.1%} p {h['perm_p']}]  "
                  f"vs 無条件金L[net {a['net']:.1f}% sh {a['sharpe']:.2f} dd {a['maxdd']:.1%}]")
            continue
        print(f"{k:12s}: keep={v['kept_frac']:.0%}  "
              f"raw[cal {v['raw']['calmar']:.2f} dd {v['raw']['maxdd']:.1%}]  "
              f"gate[cal {v['gated']['calmar']:.2f} dd {v['gated']['maxdd']:.1%} p {v['gated']['perm_p']}]  "
              f"plc[cal {v['placebo']['calmar']:.2f} dd {v['placebo']['maxdd']:.1%}]  -> {v['verdict']}")
    print("=" * 78)
    print("採用は OOS で素版をパレート支配 かつ プラセボ超 のみ。1つも無ければ『RG不採用・確定スペック維持』。")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "edge_regime_gate_10y.json"), "w") as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print("-> results/edge_regime_gate_10y.json")


if __name__ == "__main__":
    main()
