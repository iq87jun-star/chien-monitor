# -*- coding: utf-8 -*-
"""docs/244 Q242(改良系 9 + 新規 6 = 15 セル・2026-11-16 登録「未検定の所見を登録して実行」): Q240・Q241 で残った未検定の所見。
A1 = 配備形 Mon4 で「前金曜の VIX > 25 かつ 週末の窓が自分の過去の下位 20%」の通貨だけ 24h・それ以外は同日 20 UTC。X1 = E1 を GBPJPY・EURJPY・AUDJPY にだけ当て USDJPY は常に 24h。A1・X1 の基準 = 採用済みの E1。
B1 = SKEW 門(前金曜の SKEW が 252 日 80 分位超の月曜は建てない)を VIX > 25 の週には掛けない・24h(基準 = SKEW 門つき配備形)。B2 = 同・決済 E1(基準 = SKEW 門 + E1)。
C1〜C4 = US500・NAS100・US30・JP225 の月曜 13 UTC 24h から NYSE 月曜休場の日を除く、C5 = 米 3 本等分(基準 = 休場日も建てる)。見送りは損益 0。
改良系の判定 = 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
D = 金曜 12:00 UTC 売り → 同日 20:00 UTC 買い戻し(新規・docs/244 §1 の基準)。D1 = 4 本等分・木曜 VIX ≤ 25、D2 = 4 本等分・全週、D3〜D6 = 4 本それぞれ・木曜 VIX ≤ 25。
使い方: cd research && python3 -W ignore queue/q242_untested_observations_from_q240_q241.py <累積セル数>   出力: results/q242_untested_observations_from_q240_q241.csv・_new.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q237_night_leg_after_high_vix import VIX, TH
from q240_weekend_premium_predictions import frame, idx_shot, NYSE_MON, IDX3, MON4
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); D1_ = pd.Timedelta(days=1)
def fx(P, hold, skip=None):
    r = np.where(hold, P.r24, P.r20) * P.f.values * 0.25
    if skip is not None: r = np.where(skip, 0.0, r)
    return pd.Series(r, index=P.index).groupby(level=0).sum()
def fx_variant(P, kind):
    hot = P.hot.values; sk = P.skew_hi.values; one = np.ones(len(P), bool)
    return {"base": lambda: fx(P, one), "E1": lambda: fx(P, hot), "A1": lambda: fx(P, hot & P.G1.values), "X1": lambda: fx(P, hot | (P.sym == "USDJPY").values),
            "B1base": lambda: fx(P, one, sk), "B1": lambda: fx(P, one, sk & ~hot), "B2base": lambda: fx(P, hot, sk), "B2": lambda: fx(P, hot, sk & ~hot)}[kind]()
def idx_mon(sym, skip):
    b = idx_shot(sym, 0); b = b[b.index >= PRE0]; return b.where(~b.index.isin(NYSE_MON), 0.0) if skip else b
def idx3(skip):
    S = [idx_mon(s, skip) for s in IDX3]; start = max(x.index.min() for x in S); out = sum(x.reindex(pd.DatetimeIndex(sorted(set().union(*[set(x.index) for x in S])))).fillna(0.0) for x in S) / len(IDX3); return out[out.index >= start]
def fri_short(sym):
    """金曜 12:00 UTC 売り → 同日 20:00 UTC 買い戻し(コスト後)。index = 金曜の日付。"""
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 4) & (o.index.hour == 12)]; r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=8)).values); r.index = r.index.normalize(); return r[r.index >= PRE0]
def calm(idx): return (VIX.reindex(pd.DatetimeIndex(idx) - D1_, method="ffill").values <= TH)
def fri_bundle(calm_only=True):
    S = [fri_short(s) for s in MON4]; b = sum(x.reindex(pd.DatetimeIndex(sorted(set().union(*[set(x.index) for x in S])))).fillna(0.0) for x in S) / len(MON4); return b[calm(b.index)] if calm_only else b
def observation(kind):
    """紙上候補用。A1・X1・B1・B2 = 円クロス(index = 月曜)、C_<銘柄> / C_US3 = 指数、D1 = 金曜午後の売り(4 本等分・静かな週)。"""
    if kind in ("A1", "X1", "B1", "B2"): return fx_variant(frame(), kind)
    if kind == "C_US3": return idx3(True)
    if kind.startswith("C_"): return idx_mon(kind[2:], True)
    return fri_bundle(True)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 15; P = frame(); rows = []
    def judge(grp, nm, b, v, extra=""):
        s0 = max(b.index.min(), PRE0); bs = {w: stats(b, max(a, s0), e) for w, a, e in WIN}; vs = {w: stats(v, max(a, s0), e) for w, a, e in WIN}
        rows.append(dict(group=grp, cell=nm, note=extra, base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
    E1 = fx_variant(P, "E1"); B0 = fx_variant(P, "base"); hot = P.hot.values; sk = P.skew_hi.values; wk = P.groupby(level=0).agg(hot=("hot", "first"), sk=("skew_hi", "first"))
    judge("A 円クロス", "A1 VIX > 25 かつ 窓 下位 20% の通貨だけ 24h(基準 = E1)", E1, fx_variant(P, "A1"), f"24h {int((hot & P.G1.values).sum())} 本 / {int(pd.Series(hot & P.G1.values, index=P.index).groupby(level=0).any().sum())} 週")
    judge("X 円クロス", "X1 E1 を GBPJPY・EURJPY・AUDJPY にだけ・USDJPY は常に 24h(基準 = E1)", E1, fx_variant(P, "X1"))
    judge("B SKEW 門", "B1 SKEW 門を VIX > 25 の週には掛けない・24h(基準 = SKEW 門つき配備形)", fx_variant(P, "B1base"), fx_variant(P, "B1"), f"門に掛かる週 {int(wk.sk.sum())}・うち VIX > 25 は {int((wk.sk & wk.hot).sum())} 週")
    judge("B SKEW 門", "B2 SKEW 門を VIX > 25 の週には掛けない・決済 E1(基準 = SKEW 門 + E1)", fx_variant(P, "B2base"), fx_variant(P, "B2"))
    for s in IDX3 + ["JP225"]:
        b = idx_mon(s, False); judge("C 指数", f"C {s} 月曜 13 UTC 24h から NYSE 月曜休場の日を除く", b, idx_mon(s, True), f"{b.index.min().date()}〜・除いた日 {int(b.index.isin(NYSE_MON).sum())}")
    b = idx3(False); judge("C 指数", "C5 米 3 本等分から NYSE 月曜休場の日を除く", b, idx3(True), f"{b.index.min().date()}〜")
    D = pd.DataFrame(rows); D.to_csv("results/q242_untested_observations_from_q240_q241.csv", index=False)
    ref = [dict(variant=k, PRE=stats(fx_variant(P, k), *WIN[0][1:]), IS=stats(fx_variant(P, k), *WIN[1][1:]), OOS=stats(fx_variant(P, k), *WIN[2][1:])) for k in ("base", "E1", "A1", "X1", "B1base", "B1", "B2base", "B2")]
    R = Runner("Q242-D", cum + 9, 6, "results/q242_untested_observations_from_q240_q241_new.csv"); SH = []
    def addD(nm, sym, r): R.add("金曜午後の売り", sym, nm, r); SH.append(dict(cell=nm, PRE=stats(r, *WIN[0][1:]), IS=stats(r, *WIN[1][1:]), OOS=stats(r, *WIN[2][1:])))
    addD("D1 4 本等分・木曜 VIX ≤ 25", "JPY4", fri_bundle(True)); addD("D2 4 本等分・全週", "JPY4", fri_bundle(False))
    for s in MON4: x = fri_short(s); addD(f"D {s}・木曜 VIX ≤ 25", s, x[calm(x.index)])
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 80)
    print(f"Q242: cells={N} cum_before={cum} cum_after={cum + N} 改良系 passed={int((D.verdict == '成立').sum())}/9  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False)); print("\n== 参照(円クロスの各形) =="); print(pd.DataFrame(ref).to_string(index=False)); print("\n== 新規(D) =="); RD = R.finish(); print("\n== D の Sharpe / 最悪月 / 累積 / 回数 =="); print(pd.DataFrame(SH).to_string(index=False))
