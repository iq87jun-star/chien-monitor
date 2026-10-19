# -*- coding: utf-8 -*-
"""
colab_rg4h1_dukascopy.py — RG4-H1(docs/158事前登録)のDukascopy確証【ユーザーColab用】。

v7実解像度(H1・月曜04/06/08/10UTC・24h保有・間引き後EURJPY+GBPJPY)に
RG3型リスクオフ・ゲート(円バスケット日足: SMA200割れ過半×実現ボラ80分位超の週は見送り)を適用し、
docs/64 §3の防御バー(perm/同率ランダム間引きプラセボ/OOSパレート支配)で機械判定する。

使い方(Colab):
  1. 「すべて実行」。Driveマウントを許可。
  2. DRIVE_BASE/dukascopy_data_h1/{PAIR}_h1.csv(10年・UTC)を使用。
  3. 最後の「### 判定」ブロックとJSON(Drive保存)をClaude Codeセッションへ貼り付け。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR = f"{DRIVE_BASE}/dukascopy_data_h1"
OUT_JSON = f"{DRIVE_BASE}/rg4h1_dukascopy.json"

V7P = ["EURJPY", "GBPJPY"]          # 主判定(間引き後)
YEN3 = ["EURJPY", "GBPJPY", "USDJPY"]  # 参考
HOURS = [4, 6, 8, 10]               # 月曜UTC
HOLD_H = 24
COST_PIP = 2.0                      # 往復(感応1/3pip)
SMA_WIN, VOL_WIN, VOL_Q = 200, 20, 0.80
W0 = "2016-01-01"
ALPHA = 0.05                        # N=1主候補(docs/158)

try:
    if not os.path.exists("/content/drive/MyDrive"):
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
except Exception as e:
    print("Drive不可:", e)


def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001


def load_h1(pair):
    path = f"{H1_DIR}/{pair}_h1.csv"
    if not os.path.exists(path):
        print(f"⚠ {path} なし"); return None
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time", "timestamp", "date", "datetime", "gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    oc = next((c for c in ["open", "bidopen", "o"] if c in df.columns), None)
    if oc is None:
        print(f"⚠ {pair}: open列なし"); return None
    s = df[oc].astype(float)
    s = s[s.index >= W0]
    return s


def shots_weekly(pairs, cost_pip):
    """週次(週開始=月曜)の合算ショットリターン。shot = open(t)→open(t+24h)、コスト控除。"""
    legs = []
    for p in pairs:
        s = load_h1(p)
        if s is None: continue
        pipv = pip_size(p)
        mon = s[(s.index.dayofweek == 0) & (s.index.hour.isin(HOURS))]
        ex = s.reindex(mon.index + pd.Timedelta(hours=HOLD_H), method="nearest",
                       tolerance=pd.Timedelta(hours=3))
        r = (ex.values / mon.values - 1.0) - cost_pip * pipv / mon.values
        se = pd.Series(r, index=mon.index).dropna()
        wk = se.groupby(se.index.to_period("W-SUN")).sum() / len(HOURS)
        legs.append(wk.rename(p))
    if not legs: return None
    df = pd.concat(legs, axis=1)
    return df.mean(axis=1).dropna()


def daily_close(pair):
    s = load_h1(pair)
    if s is None: return None
    d = s.resample("1D").last().dropna()
    d.index = d.index.tz_localize(None)
    return d


def riskoff_weekly(pairs):
    """週次リスクオフ判定(前週金曜closeまでで確定)。True=見送り週。"""
    ups, vols = [], []
    for p in pairs:
        c = daily_close(p)
        if c is None: continue
        ups.append((c > c.rolling(SMA_WIN).mean()).rename(p))
        vols.append((np.log(c).diff().rolling(VOL_WIN).std() * np.sqrt(252)).rename(p))
    up_maj = (pd.concat(ups, axis=1).astype(float).mean(axis=1) >= 0.5)
    bv = pd.concat(vols, axis=1).mean(axis=1).dropna()
    hv = bv > bv.rolling(252, min_periods=60).quantile(VOL_Q)
    daily_off = (~up_maj) & hv
    # 週(W-SUN)ごとに「前週金曜まで」= 週開始前の最後の値で確定
    off = daily_off.resample("W-SUN").last().shift(1).fillna(False)
    off.index = pd.PeriodIndex(off.index, freq="W-SUN")
    return off.astype(bool)


def trend_weekly(pairs):
    """参考: 対称トレンドゲート(過半SMA上の週のみON)。"""
    ups = []
    for p in pairs:
        c = daily_close(p)
        if c is None: continue
        ups.append((c > c.rolling(SMA_WIN).mean()).rename(p))
    up_maj = (pd.concat(ups, axis=1).astype(float).mean(axis=1) >= 0.5)
    on = up_maj.resample("W-SUN").last().shift(1).fillna(False)
    on.index = pd.PeriodIndex(on.index, freq="W-SUN")
    return on.astype(bool)


def stats(x):
    x = np.asarray(x, float)
    net = float((1 + pd.Series(x)).prod() - 1)
    sh = float(np.mean(x) / np.std(x) * np.sqrt(52)) if np.std(x) > 0 else 0.0
    return dict(net_pct=net * 100, sharpe=sh)


def max_dd(w):
    eq = (1 + w).cumprod()
    return float((eq / eq.cummax() - 1).min())


def calmar(w):
    n = len(w)
    if n < 10: return 0.0
    ann = (1 + w).prod() ** (52.0 / n) - 1
    dd = abs(max_dd(w))
    return float(ann / dd) if dd > 1e-9 else 0.0


def perm_p_block(weekly, n_iter=8000, seed=7):
    """月次ブロック符号シャッフル"""
    m = weekly.groupby(weekly.index.asfreq("M")).sum()
    obs = m.mean(); v = m.values
    rng = np.random.default_rng(seed); cnt = 0
    for _ in range(n_iter):
        if (v * rng.choice([-1, 1], size=len(v))).mean() >= obs: cnt += 1
    return (cnt + 1) / (n_iter + 1)


def placebo_random_drop(raw, drop_frac, seed=11, reps=200):
    rng = np.random.default_rng(seed); cals, dds = [], []
    idx = raw.dropna().index
    for _ in range(reps):
        keep = rng.random(len(idx)) > drop_frac
        s = raw.loc[idx][keep]
        cals.append(calmar(s)); dds.append(max_dd(s))
    return dict(calmar=float(np.median(cals)), maxdd=float(np.median(dds)))


def split_frac(w, frac=0.7):
    k = int(len(w) * frac); return w.iloc[:k], w.iloc[k:]


def score(raw, gated, label):
    frac = 1 - len(gated) / len(raw)
    plc = placebo_random_drop(raw, frac)
    r_is, r_oos = split_frac(raw); g_is, g_oos = split_frac_align(gated, raw)
    res = dict(label=label, kept_frac=round(1 - frac, 3),
               raw=dict(**{k: round(v, 3) for k, v in stats(raw.values).items()},
                        calmar=round(calmar(raw), 3), maxdd=round(max_dd(raw), 4)),
               gated=dict(**{k: round(v, 3) for k, v in stats(gated.values).items()},
                          calmar=round(calmar(gated), 3), maxdd=round(max_dd(gated), 4),
                          perm_p=round(perm_p_block(gated), 5)),
               placebo=dict(calmar=round(plc["calmar"], 3), maxdd=round(plc["maxdd"], 4)),
               OOS=dict(raw_calmar=round(calmar(r_oos), 3), gated_calmar=round(calmar(g_oos), 3),
                        raw_maxdd=round(max_dd(r_oos), 4), gated_maxdd=round(max_dd(g_oos), 4)))
    g = dict(G_perm=res["gated"]["perm_p"] <= ALPHA,
             G_plac=(res["gated"]["calmar"] > res["placebo"]["calmar"]
                     and res["gated"]["maxdd"] > res["placebo"]["maxdd"]),
             G_pareto=(res["OOS"]["gated_calmar"] > res["OOS"]["raw_calmar"]
                       and res["OOS"]["gated_maxdd"] > res["OOS"]["raw_maxdd"]))
    res["gates"] = g
    res["verdict"] = ("ADOPT" if all(g.values())
                      else "LEAD" if (g["G_plac"] and g["G_pareto"]) else "REJECT")
    return res


def split_frac_align(gated, raw, frac=0.7):
    """ゲート版のIS/OOSを素版の暦で切る(同じ日付境界)"""
    k = int(len(raw) * frac)
    cut = raw.index[k]
    return gated[gated.index < cut], gated[gated.index >= cut]


def crisis_diag(raw, gated):
    """危機を含む分割2種のmaxDD改善(診断・採否に使わない)"""
    out = {}
    for name, lo, hi in [("2016-2021", "2016", "2021"), ("2022-2026", "2022", "2026")]:
        r = raw[(raw.index.year >= int(lo)) & (raw.index.year <= int(hi))]
        g = gated[(gated.index.year >= int(lo)) & (gated.index.year <= int(hi))]
        out[name] = dict(raw_maxdd=round(max_dd(r), 4), gated_maxdd=round(max_dd(g), 4),
                         raw_net=round(stats(r.values)["net_pct"], 2),
                         gated_net=round(stats(g.values)["net_pct"], 2))
    return out


def main():
    print("[1/3] v7ショット構築(H1・Dukascopy)")
    raw = shots_weekly(V7P, COST_PIP)
    if raw is None:
        print("⚠ H1データが読めません。DRIVE_BASEを確認してください。"); return
    raw.index = pd.PeriodIndex(raw.index, freq="W-SUN")
    off = riskoff_weekly(V7P).reindex(raw.index).fillna(False)
    gated = raw[~off]
    print(f"  週数: 素={len(raw)} ゲート後={len(gated)} 見送り率={(off.reindex(raw.index).mean()*100):.1f}%")

    print("[2/3] 採点(docs/158の防御バー)")
    res = score(raw, gated, "RG4H1_v7p(EURJPY+GBPJPY)")
    res["crisis_diag"] = crisis_diag(raw, gated)

    # 参考1: 対称トレンドゲート(採否に使わない)
    on_tr = trend_weekly(V7P).reindex(raw.index).fillna(False)
    g_tr = raw[on_tr]
    res["ref_trend_gate"] = dict(kept_frac=round(len(g_tr) / len(raw), 3),
                                 net=round(stats(g_tr.values)["net_pct"], 2),
                                 calmar=round(calmar(g_tr), 3), maxdd=round(max_dd(g_tr), 4))
    # 参考2: 3ペア版
    raw3 = shots_weekly(YEN3, COST_PIP)
    if raw3 is not None:
        raw3.index = pd.PeriodIndex(raw3.index, freq="W-SUN")
        off3 = riskoff_weekly(YEN3).reindex(raw3.index).fillna(False)
        res["ref_3pairs"] = score(raw3, raw3[~off3], "RG4H1_yen3")
    # コスト感応
    sens = {}
    for cp in (1.0, 3.0):
        r = shots_weekly(V7P, cp)
        r.index = pd.PeriodIndex(r.index, freq="W-SUN")
        o = riskoff_weekly(V7P).reindex(r.index).fillna(False)
        sc = score(r, r[~o], f"cost{cp}")
        sens[f"{cp}pip"] = dict(verdict=sc["verdict"], gates=sc["gates"])
    res["cost_sens"] = sens

    print("[3/3] 保存+判定ブロック")
    with open(OUT_JSON, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", OUT_JSON)
    print("\n### 判定(この行以下をそのまま貼り付け) ###")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
