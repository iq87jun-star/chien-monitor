# -*- coding: utf-8 -*-
"""docs/244 Q263(2026-11-17 登録「未採用のものを登録して実行」・6 セル + 診断): 方向が分かっていて未採用の現象を、まだ試していない形で確かめる(A・B・C)。口座モデルの診断(D)は q263b。
ユーザー 2026-11-17「方向性が判明しているものを教えてください」→ 一覧を回答 →「未採用のものを登録して実行」。
一覧の未採用のうち、すでに規則の形で検証済みのもの(線の下 × 直近も下げの数量 = Q258、安く始まった通貨 = Q240 / Q242、火〜木の夜の売り = Q237 / Q238)は再検証しない。未検証の形だけを登録する:
(A) 改良系 2 セル: 月曜の円クロスで「200 日線より上 かつ 短期も上向き」の通貨を建てない。Z1 = 線の下 1.0・線の上 × 5 日前より安い 0.5・線の上 × 5 日前より高い 0。Z2 = 同じ形を 20 日線で。
    判定 = 配備形(線の下 1.0・上 0.5・24h)に対して 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しない。採用候補は決済 E1 を重ねても E1 を 3 窓で上回るもの。
(B) 新規 3 セル: 円クロス 4 本の売り(4 / 6 / 8 / 10 UTC → 24h・往復 3 pip)。V1 水曜 / V2 木曜 / V3 水曜 + 木曜。判定 = 新規の標準。
(C) 改良系 1 セル: 水曜のロール(Roll5・門 2.0pp)を、日本の祝日(月〜金)がある週だけ 2 倍。判定 = 基準(全週 1.0 倍)に対する 3 窓。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q263_untested_directional_findings.py <累積セル数>   出力: results/q263_untested_directional.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import states
from q238_late_entry_after_high_vix_and_short_nights import fx_frame, MON4, HOURS
import q228_roll5_vix_x_sma200_score as q228
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); H24 = pd.Timedelta(hours=24)
def frameA():
    P = fx_frame().copy(); P["below"] = False; P["up5"] = False; P["up20"] = False
    for s in MON4:
        m = (P.sym == s).values; S = states(s).shift(1).reindex(P.index[m], method="ffill"); P.loc[m, "below"] = (S.sma200 < 0).fillna(True).values; P.loc[m, "up5"] = (S.wk > 0).fillna(False).values; P.loc[m, "up20"] = (S.sma20 > 0).fillna(False).values
    return P
def serA(P, kind, e1=False):
    f = P.f.values if kind == "base" else np.where(P.below, 1.0, np.where(P["up5" if kind == "Z1" else "up20"], 0.0, 0.5)); r = np.where(P.hot.values, P.r24, P.r20) if e1 else P.r24.values
    return pd.Series(r * f * 0.25, index=P.index).groupby(level=0).sum()
def short_days(dows):
    out = None
    for s in MON4:
        o = load(s)["open"]; acc = None
        for hh in HOURS:
            t = o.index[(o.index.dayofweek.isin(dows)) & (o.index.hour == hh)]; t = t[(t + H24).isin(o.index)]; p0 = o.reindex(t).values; r = pd.Series(-(o.reindex(t + H24).values / p0 - 1) - cost(s, p0), index=t.normalize()); acc = r if acc is None else acc.add(r, fill_value=0.0)
        x = acc / len(HOURS) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
    out = out.sort_index(); return out[out.index >= PRE0]
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; rows = []; P = frameA(); B = serA(P, "base"); E = serA(P, "base", True); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E, a, b) for w, a, b in WIN}
    print("(A) 基準:", {w: bs[w][:3] for w in bs}, "E1:", {w: es[w][:3] for w in es})
    for k, nm in (("Z1", "Z1 線の上 × 5 日前より高い通貨は建てない"), ("Z2", "Z2 線の上 × 20 日線より上の通貨は建てない")):
        v = serA(P, k); ve = serA(P, k, True); vs = {w: stats(v, a, b) for w, a, b in WIN}; ves = {w: stats(ve, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN); oke = all(ves[w][0] > es[w][0] and ves[w][1] >= es[w][1] for w, _, _ in WIN)
        sk = float((~P.below & P["up5" if k == "Z1" else "up20"]).mean()); rows.append(dict(part="A", cell=nm, PRE=vs["前窓"][:3], IS=vs["IS"][:3], OOS=vs["OOS"][:3], verdict=("成立" if ok else "不成立"), note=f"E1 重ね {ves['前窓'][:2]} / {ves['IS'][:2]} / {ves['OOS'][:2]}・E1 を 3 窓で上回る = {oke}・建てない割合 {sk * 100:.0f}%"))
    R = Runner("Q263B", cum, 3, "results/q263_untested_directional_B.csv")
    for nm, dows in (("V1 水曜の円クロス 4 本の売り 24h", [2]), ("V2 木曜の円クロス 4 本の売り 24h", [3]), ("V3 水曜 + 木曜の売り 24h", [2, 3])):
        x = short_days(dows); R.add("JpyCrossShortMidweek", "JPY4", nm, x); wk = x.groupby(x.index - pd.to_timedelta(x.index.dayofweek, unit="D")).sum(); vs = {w: stats(wk, a, b) for w, a, b in WIN}
        rows.append(dict(part="B", cell=nm, PRE=vs["前窓"][:3], IS=vs["IS"][:3], OOS=vs["OOS"][:3], verdict="(下の標準の判定)", note=f"束(1 倍)の 1 日の平均 {x.mean() * 1e4:+.2f} bps・日数 {len(x)}"))
    DB = R.finish()
    for i, r in enumerate(rows):
        if r["part"] == "B": m = DB[DB.spec == r["cell"]].iloc[0]; r["verdict"] = "通過" if m.passed else f"不通過(探索 {int(m.is_plus)} / {int(m.is_n)} か月・p {m.p:.2f}・OOS {m.oos_mean_bps:+.1f} bps・前窓 {m.pre_rate * 100:.0f}%)"
    Pr, days = q228.frame(); base_r = (Pr.r * Pr.g.astype(float)).groupby(level=0).sum().reindex(days).fillna(0.0) / len(q228.PAIRS); JH = set(pd.to_datetime(pd.read_csv("data_ext/jp_holidays_2016_2026.csv")["date"]).dt.normalize())
    hol = pd.Series([any(((d - pd.Timedelta(days=d.dayofweek)) + pd.Timedelta(days=k)) in JH for k in range(5)) for d in days], index=days); c1 = base_r * np.where(hol, 2.0, 1.0); rb = {w: stats(base_r, a, b) for w, a, b in WIN}; rc = {w: stats(c1, a, b) for w, a, b in WIN}
    act = base_r != 0; rows.append(dict(part="C", cell="C1 日本の祝日がある週のロールを 2 倍", PRE=rc["前窓"][:3], IS=rc["IS"][:3], OOS=rc["OOS"][:3], verdict=("成立" if all(rc[w][0] > rb[w][0] and rc[w][1] >= rb[w][1] for w, _, _ in WIN) else "不成立"),
                    note=f"基準 {rb['前窓'][:3]} / {rb['IS'][:3]} / {rb['OOS'][:3]}・祝日のある週 {int((hol & act).sum())} / 建てた週 {int(act.sum())}・1 週の平均 祝日あり {base_r[hol & act].mean() * 1e4:+.2f} / なし {base_r[~hol & act].mean() * 1e4:+.2f} bps"))
    D = pd.DataFrame(rows); D.to_csv("results/q263_untested_directional.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_colwidth", 150)
    print(f"\n== Q263 A・B・C(値 = Sharpe / 最悪月 % / 累積 %。累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False))
