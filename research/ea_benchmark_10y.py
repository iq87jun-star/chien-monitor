# -*- coding: utf-8 -*-
"""
ea_benchmark_10y.py — 各EA(各エッジ・各銘柄)の【個別10年数値】を同一データで横並び。

docs/53(全EA比較)の定量版。各戦略を実データ(Yahoo日足10年・研究用)で再構築し、
個別に [純益% / 勝率 / maxDD% / Sharpe / Calmar / n / 順列p / v7相関] を出す。
- 円月曜(v6/v7のエッジ): EURJPY/GBPJPY/USDJPY 各個 + バスケット
- 株指月曜(E-Mon): NAS100/US500/GER40 各個 + バスケット
- v4(D1 k≥4合議, ADOPT): FX9 合算 + ペア別件数
- E5(多資産月次TSMOM): バスケット
- v2(D1 RSI逆張り, 棄却): FX代表 — "なぜ棄却か"の数値
⚠ 規律: 数字は盛らない。日足近似ゆえ絶対値はDrive(Dukascopy/H1)で要確定。intraday(v9)・H4(v5)は
   日足から再現不可→docs値(docs/40,11)を参照欄に明記。最終確証はデモ前進検証(docs/29)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
YEN = ["EURJPY", "GBPJPY", "USDJPY"]; EMON = ["NAS100", "US500", "GER40"]
E5_BASKET = ["XAUUSD", "US500", "NAS100", "GER40"]
V4_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]


def load_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek; df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    return df


def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
def to_monthly(r):
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()
def perm_p(r, n=4000, seed=7):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n)]) >= real).mean())


def metrics(s, ann):
    s = pd.Series(s).dropna()
    if len(s) == 0: return dict(net=0, win=0, maxDD=0, sharpe=0, calmar=0, n=0, perm=1.0)
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = s.mean() * ann; vol = s.std() * np.sqrt(ann); shp = mu / vol if vol > 0 else 0
    cagr = (eq.iloc[-1] ** (ann / len(s)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    return dict(net=round(float((eq.iloc[-1] - 1) * 100), 1), win=round(float((s > 0).mean() * 100), 0),
                maxDD=round(dd, 1), sharpe=round(float(shp), 2),
                calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0, n=int(len(s)), perm=round(perm_p(s.values), 4))


# v7基準(円月曜バスケット月次)で各戦略の相関を測る
def v7_ref_monthly():
    acc = None
    for p in YEN:
        df = load_daily(p); m = to_monthly((df[df["weekday"] == 0]["o2o"] - 2 * pip(p) / df[df["weekday"] == 0]["open"]).dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0)


def corr_v7(weekly_or_monthly, ref):
    m = to_monthly(weekly_or_monthly) if weekly_or_monthly.index.freqstr != "M" else weekly_or_monthly
    j = pd.concat([m.rename("a"), ref.rename("r")], axis=1).dropna()
    return round(float(j["a"].corr(j["r"])), 2) if len(j) > 30 else None


def mon_long(name, cost_bps):
    df = load_daily(name); c = cost_bps / 1e4
    return (df[df["weekday"] == 0]["o2o"] - c).dropna()


def basket(names, cost_bps):
    parts = [mon_long(n, cost_bps).rename(n) for n in names]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def e5_monthly():
    closes = {}
    for nm in E5_BASKET:
        df = load_daily(nm); s = df["close"]; s.index = pd.to_datetime(df.index); closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12): sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    out = ((np.sign(sig).shift(1) * ret).mean(axis=1) - 5e-4).dropna(); out.index = out.index.to_period("M")
    return out


def rsi_w(c, n=14):
    d = np.diff(c, prepend=c[0]); up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1.0 / n
    for i in range(1, len(c)): au[i] = a * up[i] + (1 - a) * au[i - 1]; ad[i] = a * dn[i] + (1 - a) * ad[i - 1]
    return 100 - 100 / (1 + au / np.where(ad == 0, 1e-12, ad))


def atr_d(h, l, c, n=14):
    pc = np.roll(c, 1); pc[0] = c[0]; tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    o = np.empty_like(tr); o[0] = tr[0]; a = 1.0 / n
    for i in range(1, len(tr)): o[i] = a * tr[i] + (1 - a) * o[i - 1]
    return o


def v4_series(kmin=4, momentum=False):
    """D1 4条件 k>=kmin 合議。momentum=False=逆張り(=ADOPT版)。月次合算リターンと総件数。"""
    monthly = {}; trades = {}
    for p in V4_PAIRS:
        path = os.path.join(DATA, f"{p}_d.csv")
        if not os.path.exists(path): continue
        df = load_daily(p); o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c); rsi = rsi_w(c, 14); atr = atr_d(h, l, c, 14); bb = 20; cost = 2 * pip(p); cnt = 0
        i = bb + 2
        while i < n - 1:
            win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1); z = (c[i] - mean) / sd if sd > 0 else 0.0
            down = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
                else: break
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0; mv = 0.005
            buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(ret < -mv)
            sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(ret > mv)
            raw = 1 if (buy >= kmin and buy > sell) else (-1 if (sell >= kmin and sell > buy) else 0)
            if raw == 0: i += 1; continue
            sig = -raw if momentum else raw    # 逆張り=oversoldでLONG(raw)、momentum=継続
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0: i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
            while j < n and held < 8:
                if sig > 0:
                    if l[j] <= sl: ex = sl; break
                    if h[j] >= tp: ex = tp; break
                else:
                    if h[j] >= sl: ex = sl; break
                    if l[j] <= tp: ex = tp; break
                j += 1; held += 1
            if ex is None: ex = c[min(j, n - 1)]
            r = sig * (ex / entry - 1.0) - cost / entry
            mk = pd.Period(idx[min(j, n - 1)], freq="M"); monthly[mk] = monthly.get(mk, 0.0) + r
            cnt += 1; i = max(i + 1, j)
        trades[p] = cnt
    return pd.Series(monthly).sort_index(), trades


def v2_series():
    """v2: D1 RSI<30 で LONG / RSI>70 で SHORT(平均回帰)・5日保有。棄却の数値用(FX代表=円3+主要)。"""
    monthly = {}
    for p in ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "EURJPY"]:
        df = load_daily(p); c = df["close"].values; o = df["open"].values; idx = df.index; n = len(c); rsi = rsi_w(c, 14); cost = 2 * pip(p)
        i = 16
        while i < n - 1:
            sig = 1 if rsi[i] < 30 else (-1 if rsi[i] > 70 else 0)
            if sig == 0: i += 1; continue
            entry = o[i + 1]; j = min(i + 5, n - 1); r = sig * (c[j] / entry - 1.0) - cost / entry
            mk = pd.Period(idx[j], freq="M"); monthly[mk] = monthly.get(mk, 0.0) + r; i = j
    return pd.Series(monthly).sort_index()


def main():
    ref = v7_ref_monthly()
    rows = []

    def add(label, series, ann, note=""):
        m = metrics(series, ann); m["corr_v7"] = corr_v7(series, ref) if len(series) else None
        rows.append(dict(EA=label, **m, note=note))

    # 円月曜(v6/v7エッジ): 各個 + バスケット (円ペア往復~1.3bps)
    for p in YEN: add(f"円月曜 {p}", mon_long(p, 1.3), 52)
    add("円月曜 バスケット(v6/v7エッジ)", basket(YEN, 1.0), 52, "v7=これをリスク予算化/v6=同エッジでDD超過(docs/13)")
    # 株指月曜(E-Mon): 各個 + バスケット
    for ix in EMON: add(f"株指月曜 {ix}", mon_long(ix, 3.0), 52)
    add("株指月曜 バスケット(E-Mon)", basket(EMON, 3.0), 52, "並行ポートの核(docs/50)")
    # v4 k>=4 合議(ADOPT) と 対照(モメンタム/k>=3)
    s4, t4 = v4_series(kmin=4, momentum=False); add("v4 k>=4合議(ADOPT・逆張りD1)", s4, 12, f"件数{sum(t4.values())} {t4}")
    s4m, _ = v4_series(kmin=4, momentum=True); add("(対照)v4 k>=4 モメンタム継続", s4m, 12, "_v4.mq5系=H4版の日足対照")
    # E5
    add("E5 多資産月次TSMOM", e5_monthly(), 12, "衛星(docs/31)")
    # v2(棄却)
    add("v2 D1 RSI逆張り(棄却)", v2_series(), 12, "レジーム依存→棄却(docs/04)")

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 20)
    print("=" * 100)
    print("各EA/エッジ・各銘柄の個別10年数値(Yahoo日足10年・研究用近似)")
    print("=" * 100)
    print(df[["EA", "net", "win", "maxDD", "sharpe", "calmar", "n", "perm", "corr_v7"]].to_string(index=False))
    print("\n[日足から再現不可=docs値を参照]")
    print("  v9 (円月曜 12h intraday): net+17.9% / maxDD-5.0% / Sharpe0.76 / STRONG-LEAD (docs/40・要H1)")
    print("  v5 (H4 TSMOM)          : NO-GO 順列1/3・真maxDD-35〜-150% (docs/11・要H4)")
    print("  v4(file) H4モメンタム    : 検証段階・IS負 (docs/10・要H4)")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "ea_benchmark_10y.json"), "w") as fp:
        json.dump(df.to_dict("records"), fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/ea_benchmark_10y.json")


if __name__ == "__main__":
    main()
