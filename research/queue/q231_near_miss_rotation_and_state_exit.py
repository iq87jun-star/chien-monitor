# -*- coding: utf-8 -*-
"""docs/244 Q231(改良系・9 セル・2026-11-15 登録): 惜しくも届かなかった銘柄を、200 日線の縮小と状態別の決済で組み込み直す(第 1 段)。
(X) 月曜の円クロスを 4 本 → 7 本(+ NZDJPY・CADJPY・CHFJPY)。合計の数量は 1.0 を超えない。
    X1 = 7 本等分(各 1/7)× 線の下 1.0・上 0.5。X2 = 配備形 Mon4 + 追加 3 本は線の下のときだけ 0.25、週の合計 > 1.0 なら比例で縮小。X1e・X2e = 線の上は同日 20 UTC 決済。
    判定 = 配備形 Mon4(線の下 1.0・上 0.5・24h)に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
(F) 月曜の指数(US30・JP225・UK100・NAS100・US500・13 UTC 建て): 線の下 1.0 倍・24h / 線の上 0.5 倍・同日 20 UTC 決済。
    判定 = 常時 1.0 倍・24h に対して 3 窓 + 累積 1/2 規則(Q196 と同じ)。
使い方: cd research && python3 -W ignore queue/q231_near_miss_rotation_and_state_exit.py <累積セル数>   出力: results/q231_near_miss_rotation_and_state_exit.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q114_mon_index_intraday import shot, stats
from q194_mon_own_technical_state_gate import PAIRS as _P4, states
MON4 = list(_P4)
import deployed_book as db
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); HOURS = (4, 6, 8, 10); EXTRA = ["NZDJPY", "CADJPY", "CHFJPY"]; ALL7 = list(MON4) + EXTRA; IDX = ["US30", "JP225", "UK100", "NAS100", "US500"]
def pair_frame(s):
    """月曜 4/6/8/10 UTC 建ての 4 ショット平均。r24 = 24h 後決済(配備形)、r20 = 同日 20 UTC 決済(足が無ければ 24h)、d200 = 建て日より前の最後の日足の 終値/SMA200 − 1。"""
    h = load(s); o = h["open"]; a24 = None; a20 = None
    for hh in HOURS:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == hh)]; ok = (t + pd.Timedelta(hours=24)).isin(o.index); t = t[ok]; p0 = o.reindex(t).values; c = cost(s, p0)
        p24 = o.reindex(t + pd.Timedelta(hours=24)).values; p20 = o.reindex(t.normalize() + pd.Timedelta(hours=20)).values; r24 = p24 / p0 - 1 - c; r20 = np.where(np.isnan(p20), r24, p20 / p0 - 1 - c)
        x24 = pd.Series(r24, index=t.normalize()); x20 = pd.Series(r20, index=t.normalize()); a24 = x24 if a24 is None else a24.add(x24, fill_value=0.0); a20 = x20 if a20 is None else a20.add(x20, fill_value=0.0)
    m = pd.DataFrame({"r24": a24 / len(HOURS), "r20": a20 / len(HOURS)}).sort_index(); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]
    assert np.allclose(m.r24.values, db.mon_cell_h1(s).reindex(m.index).values, atol=1e-12), s
    m["d200"] = states(s).shift(1).reindex(m.index, method="ffill").sma200.values; return m
_F = {}
def frames():
    if not _F:
        P = {s: pair_frame(s) for s in ALL7}; idx = pd.DatetimeIndex(sorted(set().union(*[set(P[s].index) for s in MON4])))
        for k in ("r24", "r20", "d200"): _F[k] = pd.DataFrame({s: P[s][k].reindex(idx) for s in ALL7})
        _F["end"] = {s: P[s].index.max() for s in ALL7}
    return _F
def alloc(kind):
    """週 × 通貨の数量(合計 ≤ 1.0)。kind = base / X1 / X2。"""
    F = frames(); R, D = F["r24"], F["d200"]; av = R.notna(); f = pd.DataFrame(np.where(D.isna(), 1.0, np.where(D < 0, 1.0, 0.5)), index=R.index, columns=R.columns)
    if kind == "base": A = f[MON4] * 0.25 * av[MON4]; return A.reindex(columns=ALL7).fillna(0.0)
    if kind == "X1": n = av.sum(axis=1); return (f * av).div(n, axis=0).fillna(0.0)
    A = (f[MON4] * 0.25 * av[MON4]).reindex(columns=ALL7).fillna(0.0)
    for s in EXTRA: A[s] = np.where(av[s] & (D[s] < 0), 0.25, 0.0)
    tot = A.sum(axis=1); return A.mul(np.where(tot > 1.0, 1.0 / tot, 1.0), axis=0)
def x_series(kind):
    """kind = base / X1 / X2 / X1e / X2e。e = 線の上(d200 ≥ 0)の通貨は同日 20 UTC 決済。index = 月曜。"""
    F = frames(); ex = kind in ("X1e", "X2e"); A = alloc(kind[:2] if ex else kind); R = F["r24"].where(~((F["d200"] >= 0) & ex), F["r20"]); return (A * R.fillna(0.0)).sum(axis=1)
def idx_frame(s):
    r24 = shot(s, 13, None); r24 = r24[r24.index >= PRE0]; r20 = shot(s, 13, 20).reindex(r24.index); r20 = r20.fillna(r24); d = states(s).shift(1).reindex(r24.index, method="ffill").sma200
    x = pd.DataFrame({"r24": r24, "r20": r20, "d200": d}); return x[x.d200.notna()]
def f_series(s, kind="F"):
    """kind = base(常時 1.0・24h)/ F(線の下 1.0・24h、線の上 0.5・20 UTC)/ red(線の下 1.0・上 0.5・24h)/ exit(線の上だけ 20 UTC・数量同じ)/ weak(線の下のときだけ)"""
    x = idx_frame(s); lo = (x.d200 < 0).values
    return pd.Series({"base": x.r24.values, "F": np.where(lo, x.r24, 0.5 * x.r20), "red": np.where(lo, x.r24, 0.5 * x.r24), "exit": np.where(lo, x.r24, x.r20), "weak": np.where(lo, x.r24, 0.0)}[kind], index=x.index)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 9; rows = []; ref = []; F = frames(); B = x_series("base"); bs = {w: stats(B, a, b) for w, a, b in WIN}
    LAB = {"X1": "X1 円クロス 7 本等分 × 線の下 1.0・上 0.5", "X2": "X2 配備形 4 本 + 追加 3 本は線の下のときだけ(合計 ≤ 1.0)", "X1e": "X1e = X1 + 線の上は同日 20 UTC 決済", "X2e": "X2e = X2 + 線の上は同日 20 UTC 決済"}
    for k in ("X1", "X2", "X1e", "X2e"):
        v = x_series(k); vs = {w: stats(v, a, b) for w, a, b in WIN}; ok = bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))
        rows.append(dict(group="X 円クロス", cell=LAB[k], mean_size=round(float(alloc(k[:2]).sum(axis=1).mean()), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], verdict=("成立" if ok else "不成立")))
    for s in EXTRA + list(MON4):          # 参照: 通貨ごとの配備形(線の下 1.0・上 0.5・24h)と、20 UTC 決済を足した形
        d = F["d200"][s]; f = np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5)); v = (F["r24"][s] * f).dropna(); ve = (F["r24"][s].where(~(d >= 0), F["r20"][s]) * f).dropna()
        ref.append(dict(kind="通貨ごと(線の下 1.0・上 0.5)", symbol=s, end=str(F["end"][s].date()), PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:]), PRE_e=stats(ve, *WIN[0][1:]), IS_e=stats(ve, *WIN[1][1:]), OOS_e=stats(ve, *WIN[2][1:])))
    for s in IDX:
        b = f_series(s, "base"); v = f_series(s, "F"); b_ = {w: stats(b, a, e) for w, a, e in WIN}; v_ = {w: stats(v, a, e) for w, a, e in WIN}
        nm = int(b[(b.index >= PRE0) & (b.index <= PRE1)].groupby(pd.PeriodIndex(b[(b.index >= PRE0) & (b.index <= PRE1)].index, freq="M")).ngroups); use = [w for w, _, _ in WIN if not (w == "前窓" and nm < 24)]
        ok = all(v_[w][0] > b_[w][0] and v_[w][1] >= b_[w][1] for w in use); cum_ok = bool(v_["IS"][2] >= 0.5 * b_["IS"][2] and v_["OOS"][2] >= 0.5 * b_["OOS"][2])
        ver = ("成立" if ok and cum_ok else ("成立だが累積 1/2 未満" if ok else "不成立")) + ("" if "前窓" in use else "(前窓なし・参考)")
        rows.append(dict(group="F 月曜の指数", cell=f"F {s}: 線の下 1.0・24h / 線の上 0.5・20 UTC", mean_size=round(float(np.where(idx_frame(s).d200 < 0, 1.0, 0.5).mean()), 3), base_PRE=b_["前窓"], var_PRE=v_["前窓"], base_IS=b_["IS"], var_IS=v_["IS"], base_OOS=b_["OOS"], var_OOS=v_["OOS"], verdict=ver))
        for kk, kn in (("red", "線の下 1.0・上 0.5・24h"), ("exit", "線の上だけ 20 UTC 決済(数量同じ)"), ("weak", "線の下のときだけ")):
            x = f_series(s, kk); ref.append(dict(kind="指数の分解: " + kn, symbol=s, end=str(b.index.max().date()), PRE=stats(x, *WIN[0][1:]), IS=stats(x, *WIN[1][1:]), OOS=stats(x, *WIN[2][1:])))
    D = pd.DataFrame(rows); D.to_csv("results/q231_near_miss_rotation_and_state_exit.csv", index=False); RF = pd.DataFrame(ref); RF.to_csv("results/q231_near_miss_rotation_and_state_exit_ref.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 80)
    print(f"Q231: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %)"); print(D.to_string(index=False)); print("\n== 参照(判定に使わない) =="); print(RF.to_string(index=False))
    A1, A2 = alloc("X1"), alloc("X2"); print("\n追加 3 本に数量が乗る週の割合: X2", round(float((A2[EXTRA].sum(axis=1) > 0).mean()) * 100, 1), "%  X2 の追加 3 本の平均数量", round(float(A2[EXTRA].sum(axis=1).mean()), 3), " 追加 3 本の末尾", {s: str(F["end"][s].date()) for s in EXTRA})
