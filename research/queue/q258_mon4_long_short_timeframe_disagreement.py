# -*- coding: utf-8 -*-
"""docs/244 Q258(改良系・6 セル・2026-11-17 登録「登録して実行」): 月曜の円クロスで、時間軸の違う条件を掛け合わせる(長期 × 短期の向きの違い / 日足 × 当日の 1 時間足)。
ユーザー 2026-11-17「複数の時間軸で掛け合わせる事はできますか」→ 重なりを数える形(Q215)は検証済みと説明し、未検証の 2 案を提示 →「登録して実行」(番号の指定なし = 2 案とも)。
(1) 長期 × 短期: 通貨ごとに、月曜より前の最後の日足で 長期 = 終値 < 200 日線、短期 = 5 日前より高い(S5)/ 終値 > 20 日線(S20)。
    T1 = 「線の下 かつ 短期は上向き(戻り始め)」だけ 1.0 倍・ほかは 0.5 倍。T2 = 「線の下 かつ 短期も下向き(まだ下げている)」だけ 1.0 倍・ほかは 0.5 倍。× S5・S20 = 4 セル。
(2) 日足 × 当日の足: 各ショット(月曜 4・6・8・10 UTC)の直前の 1 時間足の終値が、直近 24 本の 1 時間足の平均より上か。
    I1 = 上のショットは配備形の数量のまま・下のショットは半分。I2 = 逆(下のショットはそのまま・上は半分)。2 セル。
判定(事前固定)= 配備形(200 日線の下 1.0・上 0.5・24h)に対して 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しない → 成立。
採用候補 = 成立し、かつ決済 E1 を重ねた形でも E1(0.67 / 2.31 / 1.65)に対して同じ条件を満たすもの。
参照(セル外): 長期 × 短期の 4 つの組(線の下 / 上 × 短期 上 / 下)と、1 時間足 上 / 下 の月曜の平均。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q258_mon4_long_short_timeframe_disagreement.py <累積セル数>   出力: results/q258_mon4_timeframe.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import states
from q238_late_entry_after_high_vix_and_short_nights import fx_frame, MON4, HOURS
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),); H24 = pd.Timedelta(hours=24)
def frame():
    P = fx_frame().copy(); P["below"] = False; P["up5"] = False; P["up20"] = False; P["uf"] = 1.0; P["df"] = 1.0; P["r24u"] = 0.0; P["r24d"] = 0.0; P["r20u"] = 0.0; P["r20d"] = 0.0
    for s in MON4:
        m = (P.sym == s).values; idx = P.index[m]; S = states(s).shift(1).reindex(idx, method="ffill"); P.loc[m, "below"] = (S.sma200 < 0).fillna(True).values; P.loc[m, "up5"] = (S.wk > 0).fillna(False).values; P.loc[m, "up20"] = (S.sma20 > 0).fillna(False).values
        h = load(s); o = h["open"]; c = h["close"]; up = (c > c.rolling(24).mean()).shift(1); acc = {k: pd.Series(0.0, index=idx) for k in ("r24u", "r24d", "r20u", "r20d", "nu")}
        for hh in HOURS:
            t = o.index[(o.index.dayofweek == 0) & (o.index.hour == hh)]; t = t[(t + H24).isin(o.index)]; p0 = o.reindex(t).values; cst = cost(s, p0); r24 = o.reindex(t + H24).values / p0 - 1 - cst; p20 = o.reindex(t.normalize() + pd.Timedelta(hours=20)).values; r20 = np.where(np.isnan(p20), r24, p20 / p0 - 1 - cst)
            u = up.reindex(t).fillna(False).values.astype(bool); d = pd.DataFrame({"r24u": np.where(u, r24, 0.0), "r24d": np.where(u, 0.0, r24), "r20u": np.where(u, r20, 0.0), "r20d": np.where(u, 0.0, r20), "nu": u.astype(float)}, index=t.normalize())
            for k in acc: acc[k] = acc[k].add(d[k].reindex(idx).fillna(0.0), fill_value=0.0)
        for k in ("r24u", "r24d", "r20u", "r20d"): P.loc[m, k] = (acc[k] / len(HOURS)).values
        P.loc[m, "nu"] = acc["nu"].values
        assert np.allclose((P.r24u + P.r24d)[m].values, P.r24[m].values, atol=1e-12), s
    return P
def fac(P, kind):
    b, u5, u20 = P.below.values, P.up5.values, P.up20.values
    return {"base": P.f.values, "T1_S5": np.where(b & u5, 1.0, 0.5), "T2_S5": np.where(b & ~u5, 1.0, 0.5), "T1_S20": np.where(b & u20, 1.0, 0.5), "T2_S20": np.where(b & ~u20, 1.0, 0.5)}[kind]
def series(P, kind, e1=False):
    if kind in ("I1", "I2"):
        wu, wd = (1.0, 0.5) if kind == "I1" else (0.5, 1.0); r24 = wu * P.r24u + wd * P.r24d; r20 = wu * P.r20u + wd * P.r20d; f = P.f.values
    else: r24, r20, f = P.r24, P.r20, fac(P, kind)
    r = np.where(P.hot.values, r24, r20) if e1 else r24; return pd.Series(np.asarray(r) * f * 0.25, index=P.index).groupby(level=0).sum()
LAB = {"T1_S5": "T1 線の下 かつ 5 日前より高い だけ 1.0 倍", "T2_S5": "T2 線の下 かつ 5 日前より安い だけ 1.0 倍", "T1_S20": "T1 線の下 かつ 20 日線より上 だけ 1.0 倍", "T2_S20": "T2 線の下 かつ 20 日線より下 だけ 1.0 倍", "I1": "I1 1 時間足が 24 本平均より上のショットはそのまま・下は半分", "I2": "I2 1 時間足が 24 本平均より下のショットはそのまま・上は半分"}
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; P = frame(); rows = []; ref = []
    B = series(P, "base"); E = series(P, "base", True); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E, a, b) for w, a, b in WIN}
    print("基準(0.46 / 1.51 / 1.20 のはず):", {w: bs[w][:3] for w in bs}, " E1(0.67 / 2.31 / 1.65 のはず):", {w: es[w][:3] for w in es})
    for k in LAB:
        v = series(P, k); ve = series(P, k, True); vs = {w: stats(v, a, b) for w, a, b in WIN}; ves = {w: stats(ve, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN); oke = all(ves[w][0] > es[w][0] and ves[w][1] >= es[w][1] for w, _, _ in WIN)
        rows.append(dict(cell=LAB[k], var_PRE=vs["前窓"][:3], var_IS=vs["IS"][:3], var_OOS=vs["OOS"][:3], verdict=("成立" if ok else "不成立"), withE1_PRE=ves["前窓"][:3], withE1_IS=ves["IS"][:3], withE1_OOS=ves["OOS"][:3], beats_E1=bool(oke), candidate=bool(ok and oke)))
    D = pd.DataFrame(rows); D.to_csv("results/q258_mon4_timeframe.csv", index=False)
    def add(tab, grp, y, w):
        y = y.dropna(); wk = y.groupby(level=0).mean(); ref.append(dict(table=tab, group=grp, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t_week=round(float(wk.mean() / wk.std() * np.sqrt(len(wk))), 2) if len(wk) > 2 and wk.std() > 0 else None))
    for w, a, b in ALLW:
        z = P[(P.index >= a) & (P.index <= b)]
        for sk, lab in (("up5", "5 日"), ("up20", "20 日線")):
            for g, m in ((f"線の下 × 短期({lab})上向き", z.below & z[sk]), (f"線の下 × 短期({lab})下向き", z.below & ~z[sk]), (f"線の上 × 短期({lab})上向き", ~z.below & z[sk]), (f"線の上 × 短期({lab})下向き", ~z.below & ~z[sk])): add("長期 × 短期(1 倍・24h)", g, z.r24[m], w)
        nu = z.nu.clip(lower=1e-9); nd = (len(HOURS) - z.nu).clip(lower=1e-9); add("1 時間足(ショット単位・1 倍・24h)", "24 本平均より上のショット", (z.r24u * len(HOURS) / nu)[z.nu > 0], w); add("1 時間足(ショット単位・1 倍・24h)", "24 本平均より下のショット", (z.r24d * len(HOURS) / nd)[z.nu < len(HOURS)], w)
    R = pd.DataFrame(ref); R.loc[R.table.str.startswith("1 時間足"), "t_week"] = None          # ショット数で重みが変わるため、この表は平均だけを使う(t は出さない)
    R.to_csv("results/q258_mon4_timeframe_ref.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 200)
    print(f"\n== 判定(値 = Sharpe / 最悪月 % / 累積 %。累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False)); print("\n== 参照 =="); print(R.pivot_table(index=["table", "group"], columns="window", values=["mean_bps", "t_week", "n"], aggfunc="first", sort=False).to_string())
