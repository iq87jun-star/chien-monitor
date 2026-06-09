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
    out["weekday"] = out.index.dayofweek
    out = out[out["weekday"] <= 4].copy()
    out["o2o"] = out["open"].shift(-1) / out["open"] - 1.0     # open->翌open
    return out


CACHE = {}
def load(name):
    if name not in CACHE:
        p = os.path.join(LOCAL, f"{name}_d.csv")
        CACHE[name] = _read_ohlc(p) if os.path.exists(p) else None
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

def emon_weekly_gated(kind, cost_mult=1.0):
    """kind in {trend, vol, riskoff}. レジームでその週の各レッグをON/OFF。"""
    high = basket_vol_high(EMON) if kind in ("vol", "riskoff") else None
    legs = []
    for nm in EMON:
        df = load(nm)
        if df is None: continue
        c = BASE_BPS * 1e-4 * cost_mult
        mon = df[df["weekday"] == WD_MON].copy()
        leg = (mon["o2o"] - c)
        up = sma_above(df["close"]).reindex(mon.index).fillna(False)
        hv = (high.reindex(mon.index).fillna(False) if high is not None else pd.Series(False, index=mon.index))
        if kind == "trend":
            on = up
        elif kind == "vol":
            on = ~hv
        elif kind == "riskoff":
            on = ~((~up) & hv)            # SMA割れ かつ 高ボラ の週だけ OFF
        else:
            on = pd.Series(True, index=mon.index)
        legs.append(leg.where(on.astype(bool), np.nan).rename(nm))
    if not legs: return None
    return pd.concat(legs, axis=1).mean(axis=1).dropna()

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


def main():
    if not os.path.isdir(LOCAL):
        print("research/data が無い。Drive/ローカルにFX/指数/金の *_d.csv を置いて再実行。")
        return
    out = {}
    raw = emon_weekly_raw()
    out["RG1_TREND"]   = score_gate("RG1_TREND",   raw, emon_weekly_gated("trend"))
    out["RG2_VOL"]     = score_gate("RG2_VOL",     raw, emon_weekly_gated("vol"))
    out["RG3_RISKOFF"] = score_gate("RG3_RISKOFF", raw, emon_weekly_gated("riskoff"))
    # RG4/RG5/RG6 は Drive の v7(H1)/金/ポート合算が要るためフック（データ接続後に有効化）
    out["RG4_V7"]   = dict(id="RG4_V7",   status="PENDING_DRIVE_v7_h1")
    out["RG5_GOLD"] = dict(id="RG5_GOLD", status="PENDING_DRIVE_xau_riskoff")
    out["RG6_VTGT"] = dict(id="RG6_VTGT", status="PENDING_DRIVE_portfolio_blend")

    print(f"RG 事前登録ハーネス (N={N_CAND}, Bonferroni α={ALPHA_BONF:.4f}) — 素版 vs ゲート版 vs プラセボ")
    print("=" * 78)
    for k, v in out.items():
        if v.get("status"):
            print(f"{k:12s}: {v['status']}"); continue
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
