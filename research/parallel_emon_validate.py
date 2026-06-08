# -*- coding: utf-8 -*-
"""
parallel_emon_validate.py — 並行ポートフォリオ核 "E-Mon(株価指数 月曜LONG)" を v7基準9ゲートで採点。

parallel_edge_hunt_10y.py で唯一生き残った無相関の新エッジ = 株価指数の月曜効果(E-Mon)。
本スクリプトは docs/40 と同一の9ゲートを E-Mon に課し、v7 と同じ STRONG-LEAD に届くかを正直に採点する。
さらに E-Mon ⇄ v7(円月曜) ⇄ E5(多資産TSMOM) の月次相関を測り、並行ポートフォリオの分散効果を確認する。

E-Mon定義: NAS100/US500/GER40 の月曜 open→翌open LONG を等加重(円3クロスのv7と対称な"指数3つ"バスケット)。
規律: 数字は盛らない。最終はDukascopy/足内+デモ前進検証。指数=配当除く近似・コストはbps控除。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
EMON = ["NAS100", "US500", "GER40"]
E5_BASKET = ["XAUUSD", "US500", "NAS100", "GER40"]   # edge5/E5 MA2(金+指数, 暗号除く)
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "XAUUSD": 4.0}
WD = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def load_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    return df


def perm_p(rets, n_iter=8000, seed=7):
    rets = np.asarray(rets, float)
    if len(rets) == 0:
        return 1.0
    rng = np.random.default_rng(seed); real = rets.sum(); s = np.abs(rets)
    null = np.array([(s * rng.choice([-1, 1], size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())


def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0, sharpe=0)
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    shp = float(x.mean() / x.std() * np.sqrt(52)) if x.std() > 0 else 0.0   # 週次→年率近似
    return dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), win_pct=round((x > 0).mean() * 100, 0),
                maxDD_pct=round(dd, 1), n=int(len(x)), sharpe=round(shp, 2))


def to_monthly(r):
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()


def dow_basket(names, wd, cost_mult=1.0):
    """names の wd 曜日 open→翌open LONG 等加重。日付indexの週次リターンSeries。"""
    parts = []
    for nm in names:
        df = load_daily(nm)
        c = COST_BPS.get(nm, 4.0) * cost_mult / 1e4
        r = (df[df["weekday"] == wd]["o2o"] - c).dropna()
        parts.append(r.rename(nm))
    j = pd.concat(parts, axis=1)
    return j.mean(axis=1, skipna=True).dropna()   # 等加重(同日に揃う指数の平均)


# v7(円月曜)プロキシ
def v7_weekly():
    parts = []
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        df = load_daily(p)
        parts.append((df[df["weekday"] == 0]["o2o"] - 2e-4).rename(p))
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


# E5(多資産月次TSMOM, MA2=金+指数)プロキシ
def e5_monthly():
    closes = {}
    for nm in E5_BASKET:
        df = pd.read_csv(os.path.join(DATA, f"{nm}_d.csv"))
        df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        s = df.dropna(subset=["t"]).set_index("t")["close"].sort_index()
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna()
    ret = px.pct_change()
    sig = pd.DataFrame(index=px.index, columns=px.columns, dtype=float)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    sig = np.sign(sig)                       # 多ルックバック多数決の符号
    pos = sig.shift(1)                       # 翌月にポジション(no-lookahead)
    pnl = (pos * ret).mean(axis=1) - 5e-4    # 等加重・コスト5bps
    out = pnl.dropna(); out.index = out.index.to_period("M")
    return out


def gate_score(emon_w):
    """E-Mon週次リターンに9ゲートを当てる。"""
    full = stats(emon_w.values)
    p_full = perm_p(emon_w.values)
    # 多重検定N=130(探索全体)→Bonferroni
    alpha = 0.05 / 130
    # G4 プラセボ: 同じ指数3つの他曜日。月曜だけ有意ならOK。
    placebo = {}
    for wd in range(5):
        r = dow_basket(EMON, wd)
        placebo[WD[wd]] = dict(net=stats(r.values)["net_pct"], p=round(perm_p(r.values), 4))
    # G5 ジャックナイフ(全年)
    yrs = sorted(set(pd.to_datetime(emon_w.index).year))
    jk = {int(y): round(perm_p(emon_w[pd.to_datetime(emon_w.index).year != y].values), 3) for y in yrs}
    jk_max = max(jk.values())
    # G6 IS/OOS(70:30)
    cut = emon_w.index[int(len(emon_w) * 0.7)]
    is_ = stats(emon_w[emon_w.index < cut].values); oos = stats(emon_w[emon_w.index >= cut].values)
    # G7 WF(5分割, +の期数)
    chunks = np.array_split(np.arange(len(emon_w)), 5)
    wf = [round((1 + emon_w.iloc[idx]).prod() - 1, 4) for idx in chunks]
    wf_pos = sum(1 for v in wf if v > 0)
    # G8 コスト2×
    r2 = dow_basket(EMON, 0, cost_mult=2.0); cost2 = stats(r2.values)["net_pct"]
    # G9 −10%枠適合: 月次集約してブロックブートストラップで p95 年次maxDD を、週次サイズ係数で
    mon = to_monthly(emon_w)
    # 代表サイズ: 1トレード(=1指数1月曜)あたり口座リスクを s%。バスケットは月4-5トレード。
    # ここでは「素のバスケット月次」を任意倍率kで年次p95 maxDDが-10%に収まるkを探索。
    def p95_maxdd(scale, n_year=12, n_boot=4000, seed=3):
        rng = np.random.default_rng(seed); arr = mon.values * scale
        dds = []
        for _ in range(n_boot):
            path = rng.choice(arr, size=n_year, replace=True)
            eq = np.cumprod(1 + path); dd = ((eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)).min()
            dds.append(dd)
        return float(np.percentile(dds, 5) * 100)   # 5パーセンタイル=p95悪化側
    # 素バスケットの年次p95 maxDD と、-10%に収めるスケール
    base_p95 = p95_maxdd(1.0)
    scale_10 = 1.0
    for k in np.linspace(0.1, 1.5, 29):
        if p95_maxdd(k) >= -10.0:
            scale_10 = k
    return dict(full=full, perm_p=round(p_full, 5), alpha_bonf=round(alpha, 6),
                placebo=placebo, jackknife=jk, jk_max=jk_max, IS=is_, OOS=oos,
                wf=wf, wf_pos=wf_pos, cost2_net=cost2,
                base_p95_maxdd=round(base_p95, 1), scale_to_10pct=round(scale_10, 2))


def main():
    emon = dow_basket(EMON, 0)
    g = gate_score(emon)

    # 相関(月次)
    em_m = to_monthly(emon); v7_m = to_monthly(v7_weekly()); e5_m = e5_monthly()
    def corr(a, b):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        return round(float(j["a"].corr(j["b"])), 3) if len(j) > 30 else None
    cor_v7 = corr(em_m, v7_m); cor_e5 = corr(em_m, e5_m); cor_v7e5 = corr(v7_m, e5_m)

    # 並行ポートフォリオ: E-Mon核 + E5衛星 のブレンドDD(月次, 等リスク近似で比率振り)
    def blend_dd(wA, wB, a, b, target=None):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        # 各レッグを標準化(同ボラ)してから比率
        sa = j["a"] / j["a"].std(); sb = j["b"] / j["b"].std()
        port = wA * sa + wB * sb
        eq = (1 + port * 0.01).cumprod()   # 任意スケール(相対比較用)
        dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
        return round(dd, 2), round(float(port.mean() / port.std() * np.sqrt(12)), 2)

    blends = {}
    for ra, rb in [(100, 0), (70, 30), (60, 40), (50, 50)]:
        dd, shp = blend_dd(ra / 100, rb / 100, em_m, e5_m)
        blends[f"EMon{ra}:E5{rb}"] = dict(rel_maxDD=dd, rel_sharpe=shp)

    print("=" * 78)
    print("E-Mon (株価指数 月曜LONG: NAS100/US500/GER40 等加重) — v7基準9ゲート採点")
    print("=" * 78)
    f = g["full"]
    print(f"全期間: 純益{f['net_pct']}% 勝率{f['win_pct']}% maxDD{f['maxDD_pct']}% Sharpe{f['sharpe']} n={f['n']}")
    print(f"G3 perm_p = {g['perm_p']}  (Bonferroni α={g['alpha_bonf']})  → {'合格' if g['perm_p']<=g['alpha_bonf'] else '未達(=STRONG-LEAD)'}")
    print(f"G4 プラセボ(曜日別 純益% / perm_p):")
    for k, v in g["placebo"].items():
        print(f"     {k}: {v['net']:>7}%  p={v['p']}")
    print(f"G5 ジャックナイフ max_p = {g['jk_max']}  → {'合格(<=0.10)' if g['jk_max']<=0.10 else '未達'}")
    print(f"     年別: {g['jackknife']}")
    print(f"G6 IS 純益{g['IS']['net_pct']}% / OOS 純益{g['OOS']['net_pct']}% DD{g['OOS']['maxDD_pct']}% → {'両方+で減衰なし' if g['IS']['net_pct']>0 and g['OOS']['net_pct']>0 else '減衰'}")
    print(f"G7 WF 5分割の各期リターン: {g['wf']}  → {g['wf_pos']}/5 が +")
    print(f"G8 コスト2×での純益 = {g['cost2_net']}%  → {'+維持' if g['cost2_net']>0 else 'マイナス'}")
    print(f"G9 −10%適合: 素バスケット年次p95 maxDD = {g['base_p95_maxdd']}% / −10%に収めるスケール = {g['scale_to_10pct']}x")
    print()
    print("相関(月次・10年):")
    print(f"     E-Mon ⇄ v7(円月曜)   = {cor_v7}   ← 並行ポートの肝(低いほど良い)")
    print(f"     E-Mon ⇄ E5(多資産TSMOM) = {cor_e5}")
    print(f"     v7   ⇄ E5             = {cor_v7e5}")
    print()
    print("並行ポートフォリオ内ブレンド(E-Mon核 + E5衛星, 等ボラ標準化, 相対値):")
    for k, v in blends.items():
        print(f"     {k}: 相対maxDD {v['rel_maxDD']}  相対Sharpe {v['rel_sharpe']}")

    out = dict(emon_full=f, gates=g, corr=dict(emon_v7=cor_v7, emon_e5=cor_e5, v7_e5=cor_v7e5), blends=blends)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "parallel_emon_validate.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/parallel_emon_validate.json")


if __name__ == "__main__":
    main()
