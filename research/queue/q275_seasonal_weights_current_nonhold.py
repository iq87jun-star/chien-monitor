# -*- coding: utf-8 -*-
"""docs/244 Q275(2026-11-24 登録「登録して実行」・セル 4): 保有以外のいまの手法で「季節」の配分を作る。
ユーザー 2026-11-24「季節は現在保有の手法で長期保有以外のもので作成できますか」→「登録して実行」。
枠(月次・倍率 1・Q274 と同じ Yahoo 日足): 月曜の円クロス 4 本 / 月曜の米国指数(NAS100・US500)/ 月曜の JP225 / FX の逆張り v4(9 ペア)。
決め方: (i) 元のまま = R4(平均月利 ≥ 0.5% の枠を 平均 ÷ 標準偏差 で比例)・R3a(固定 75% + R1 25%)。(ii) 尺度をそろえる = 各枠を学習年の月次の標準偏差 1% に合わせてから
        R4′(暦月ごとの 平均 ÷ 標準偏差 ≥ 0.5 の枠をその値に比例)・R3a′(固定 75% + R4′ 25%)。固定配分は 4 分の 1 ずつ。
期間: ① 2016〜2025(年を抜いて重みと拡大率を決める)② 2026-01〜10(2016〜2025 で固定)。
判定: 基準 = 同じ決め方の固定配分。①② の両方で Sharpe が基準 + 0.10 以上、全 130 か月の最悪月(変動を基準にそろえた後)が悪化しない、偽の重み(月の入れ替え 200 回・乱数 7)に対して p < 0.05 → 変更候補。
参照: GER40 ブレイク(Dukascopy 1 時間足・〜2026-08)を足した 5 枠 / 重みの表 / 年別。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q275_seasonal_weights_current_nonhold.py <累積セル数>   出力: results/q275_seasonal_weights_nonhold.csv・results/q275_seasonal_weights_table.csv"""
import os, sys
_ARGV = list(sys.argv)
import numpy as np, pandas as pd
import q274_seasonal_r4_rebuild as q4
so, pv, base = q4.so, q4.pv, q4.base
YEARS = so.LOYO_YEARS; REPS, SEED, RV_MIN = 200, 7, 0.5
def mon_basket(names):
    parts = [(pv.load_daily(nm)[pv.load_daily(nm)["weekday"] == 0]["o2o"] - base.IDX_COST[nm]).rename(nm) for nm in names]
    return pv.to_monthly(pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna())
def ger40_breakout():
    import q_common as qc
    src = open(os.path.join(qc.ROOT, "queue", "q52_donchian_vs_hold.py"), encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]; ns = {"__name__": "q52_head"}; exec(compile(src, "q52_head", "exec"), ns)
    r = ns["donchian"]("GER40", 120, "trail2ATR"); m = r.groupby(pd.PeriodIndex(r.index, freq="M")).sum(); return m
def sleeves(with_ger=False, end="2026-10"):
    S = {"月曜の円クロス": q4.mon4(), "月曜の米国指数": mon_basket(["NAS100", "US500"]), "月曜の JP225": mon_basket(["JP225"]), "FX の逆張り": pv.v4_monthly()}
    if with_ger: S["GER40 ブレイク"] = ger40_breakout()
    df = pd.DataFrame(S); df = df[(df.index >= pd.Period("2016-01", "M")) & (df.index <= pd.Period(end, "M"))]; return df.fillna(0.0)
def weights(dft, years, rule):
    """dft = 学習に使う月次(group ii では拡大・縮小後)。返り値 {月: {枠: 重み}}"""
    mu, sd = so.month_stats(dft, years); k = len(dft.columns); out = {}
    for m in range(1, 13):
        if rule in ("R0", "R1", "R4", "R3a"): out[m] = so.weights_for(rule, mu.loc[m], sd.loc[m])
        else:
            rv = (mu.loc[m] / sd.loc[m].replace(0, np.nan)).dropna(); sel = rv[rv >= RV_MIN]; w4 = {} if sel.empty else (sel / sel.sum()).to_dict(); w0 = {c: 1.0 / k for c in dft.columns}
            if rule == "R0s": out[m] = w0
            elif rule == "R4s": out[m] = w4
            elif rule == "R3as":
                w = {c: 0.25 * w4.get(c, 0.0) + 0.75 * w0[c] for c in dft.columns}; s = sum(w.values()); out[m] = {c: v / s for c, v in w.items()}
            else: raise ValueError(rule)
    return out
def run(df, rule, scaled, shuffle_rule=None, rng=None):
    """① 年を抜いた系列(2016〜2025)と ② 2026 年(2016〜2025 で固定)。shuffle_rule: 月 → 重みの対応を入れ替える対象の型(偽の重み)。"""
    L = df[(df.index.year >= 2016) & (df.index.year <= 2025)]; out1 = []
    def w_of(train_df, years):
        W = weights(train_df, years, rule)
        if shuffle_rule is not None:
            Wb = weights(train_df, years, shuffle_rule); perm = rng.permutation(range(1, 13)); Wp = {m: Wb[perm[m - 1]] for m in range(1, 13)}
            if rule == shuffle_rule: W = Wp
            else:   # R3a / R3as: 固定 75% + 入れ替えた月別 25%
                W0 = weights(train_df, years, "R0" if rule == "R3a" else "R0s"); W = {}
                for m in range(1, 13):
                    keys = set(Wp[m]) | set(W0[m]); w = {c: 0.25 * Wp[m].get(c, 0.0) + 0.75 * W0[m].get(c, 0.0) for c in keys}; s = sum(w.values()); W[m] = {c: v / s for c, v in w.items()} if s > 0 else {}
        return W
    for y in YEARS:
        tr = [t for t in YEARS if t != y]; sc = (0.01 / L[[i.year in tr for i in L.index]].std()) if scaled else 1.0; W = w_of(L * sc, tr); out1.append(q4.apply(L[L.index.year == y] * sc, W))
    s1 = pd.concat(out1).sort_index(); sc = (0.01 / L.std()) if scaled else 1.0; Wall = w_of(L * sc, YEARS); d26 = df[df.index.year == 2026]; s2 = q4.apply(d26 * sc, Wall) if len(d26) else pd.Series(dtype=float)
    return s1, s2, Wall
def sharpe(s): return float(s.mean() / s.std() * np.sqrt(12)) if len(s) > 2 and s.std() > 0 else 0.0
def block(df, tag, judged, rows, tabs):
    so.FIXED_R0 = {c: 1.0 / len(df.columns) for c in df.columns}; rng = np.random.default_rng(SEED)
    for grp, scaled, base_rule, arms in (("(i) 元の決め方", False, "R0", (("R4", "R4"), ("R3a", "R1"))), ("(ii) 尺度をそろえる", True, "R0s", (("R4s", "R4s"), ("R3as", "R4s")))):
        b1, b2, _ = run(df, base_rule, scaled); ball = pd.concat([b1, b2]); bw = float(ball.min() * 100)
        def rec(nm, s1, s2, cells, verdict, p=np.nan):
            allm = pd.concat([s1, s2]); k = ball.std() / allm.std() if allm.std() > 0 else 0.0; a1, a2, aa = q4.st(s1), q4.st(s2), q4.st(allm)
            rows.append(dict(universe=tag, group=grp, arm=nm, mean_month_1=a1["mean_month_pct"], sharpe_1=a1["sharpe"], maxDD_1=a1["maxDD"], worst_1=a1["worst_month_pct"], sum_2026=round(float(s2.sum() * 100), 2), sharpe_2=a2["sharpe"], maxDD_2=a2["maxDD"],
                             sharpe_all=aa["sharpe"], ann_all=aa["ann_pct"], maxDD_all=aa["maxDD"], worst_all_volmatched=round(float((allm * k).min() * 100), 2), ann_all_volmatched=q4.st(allm * k)["ann_pct"], placebo_p=p, cells=cells, verdict=verdict))
            return a1["sharpe"], a2["sharpe"], round(float((allm * k).min() * 100), 2)
        sb1, sb2, _ = rec("固定配分(基準)", b1, b2, 0, "基準")
        for rule, shuf in arms:
            s1, s2, Wall = run(df, rule, scaled); real = sharpe(s1); dist = np.array([sharpe(run(df, rule, scaled, shuffle_rule=shuf, rng=rng)[0]) for _ in range(REPS)]); p = float((dist >= real).mean())
            a1s, a2s, wm = q4.st(s1)["sharpe"], q4.st(s2)["sharpe"], round(float((pd.concat([s1, s2]) * (ball.std() / pd.concat([s1, s2]).std())).min() * 100), 2)
            ok = (a1s >= sb1 + 0.10) and (a2s >= sb2 + 0.10) and (wm >= round(bw, 2)) and (p < 0.05)
            nm = {"R4": "R4(月別・元の線 0.5%)", "R3a": "R3a(固定 75% + 月別 25%)", "R4s": "R4′(月別・平均 ÷ 標準偏差 ≥ 0.5)", "R3as": "R3a′(固定 75% + R4′ 25%)"}[rule]
            rec(nm, s1, s2, 1 if judged else 0, ("変更候補" if ok else "現行どおり") if judged else "—", round(p, 3))
            if rule in ("R4", "R4s"):
                for m in range(1, 13): tabs.append(dict(universe=tag, group=grp, month=m, **{c: round(float(Wall[m].get(c, 0.0)), 3) for c in df.columns}))
            print("done", tag, grp, rule, flush=True)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 4; rows = []; tabs = []
    df = sleeves(); L = df[df.index.year <= 2025]
    print(f"枠の月次 {df.index[0]}〜{df.index[-1]}({len(df)} か月)。平均月利 %(2016〜2025): {(L.mean() * 100).round(3).to_dict()}・月次の標準偏差 %: {(L.std() * 100).round(2).to_dict()}・Sharpe: {(L.mean() / L.std() * np.sqrt(12)).round(2).to_dict()}")
    print("枠どうしの月次の相関:"); print(L.corr().round(2).to_string())
    print("暦月別の平均月利 %(2016〜2025):"); print((L.groupby(L.index.month).mean() * 100).round(2).T.to_string())
    m4 = q4.mon4(); assert np.allclose(df["月曜の円クロス"].values, m4.reindex(df.index).fillna(0.0).values)
    block(df, "4 枠(判定)", True, rows, tabs)
    dg = sleeves(with_ger=True, end="2026-08"); print(f"\n参照 5 枠: GER40 ブレイクの平均月利 %(2016〜2025) {dg[dg.index.year <= 2025]['GER40 ブレイク'].mean() * 100:.3f}・{dg.index[0]}〜{dg.index[-1]}"); block(dg, "参照: 5 枠(GER40 ブレイクを足す・2026-08 まで)", False, rows, tabs)
    D = pd.DataFrame(rows); D.to_csv("results/q275_seasonal_weights_nonhold.csv", index=False); T = pd.DataFrame(tabs).fillna(0.0); T.to_csv("results/q275_seasonal_weights_table.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 44); pd.set_option("display.max_rows", 200)
    print(f"\n== Q275(累積セル {cum} + {N} = {cum + N}・倍率 1・_1 = 2016〜2025(年を抜く)・_2 = 2026(2016〜2025 で固定)) =="); print(D.to_string(index=False))
    print("\n重みの表(2016〜2025 で決めた場合・4 枠):"); print(T[T.universe.str.startswith("4")].drop(columns=["universe"]).to_string(index=False))
    for grp, scaled, rules in (("(i)", False, ("R0", "R4", "R3a")), ("(ii)", True, ("R0s", "R4s", "R3as"))):
        so.FIXED_R0 = {c: 0.25 for c in df.columns}; Y = pd.DataFrame({r: pd.concat(run(df, r, scaled)[:2]).groupby(lambda p: p.year).sum() * 100 for r in rules}).round(1); print(f"\n年別の合計 % {grp}:"); print(Y.T.to_string())
    j = D[D.cells == 1]; print(f"\n判定: 変更候補 {int((j.verdict == '変更候補').sum())} / {len(j)} 件")
