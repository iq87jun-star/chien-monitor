# -*- coding: utf-8 -*-
"""docs/244 Q238(改良系・6 セル・2026-11-16 登録「登録して実行」): 捉えた特徴を建てる側に使う。
(L) 前金曜の VIX > 25 の週は月曜 20:00 UTC に建てて夜だけ持つ(決済は元の時刻)。25 以下の週は元の形。
    L1 = 円クロス(配備形 Mon4)。L2 = 円クロスで 25 以下の週は同日 20 UTC 決済(E1)・25 超の週は夜だけ。L3〜L5 = 月曜の指数 NAS100・US500・US30(13 UTC 建て・24h)。
(S) S1 = 配備形 Mon4 + 前日の VIX > 25 の火〜木の夜(20 UTC → 翌 13 UTC)の NAS100・US500 の売り(合計 0.25)。
判定 = 各基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない(指数は累積 1/2 規則)。
使い方: cd research && python3 -W ignore queue/q238_late_entry_after_high_vix_and_short_nights.py <累積セル数>   出力: results/q238_late_entry_after_high_vix.csv・_parts.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q114_mon_index_intraday import shot, stats as stats3
from q194_mon_own_technical_state_gate import PAIRS as _P4, states
from q237_night_leg_after_high_vix import night, VIX, TH
import deployed_book as db
MON4 = list(_P4); IDX = ["NAS100", "US500", "US30"]; HOURS = (4, 6, 8, 10)
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def fx_frame():
    """通貨 × 月曜: r24(配備形)・r20(同日 20 UTC 決済)・rN(20 UTC 建て → 元の決済時刻)。いずれも往復コスト 1 回込み・4 ショット平均。"""
    rows = []
    for s in MON4:
        h = load(s); o = h["open"]; acc = {}
        for hh in HOURS:
            t = o.index[(o.index.dayofweek == 0) & (o.index.hour == hh)]; ok = (t + pd.Timedelta(hours=24)).isin(o.index); t = t[ok]; p0 = o.reindex(t).values; c = cost(s, p0)
            p24 = o.reindex(t + pd.Timedelta(hours=24)).values; p20 = o.reindex(t.normalize() + pd.Timedelta(hours=20)).values; r24 = p24 / p0 - 1 - c
            d = pd.DataFrame({"r24": r24, "r20": np.where(np.isnan(p20), r24, p20 / p0 - 1 - c), "rN": np.where(np.isnan(p20), r24, p24 / p20 - 1 - c)}, index=t.normalize())
            for k in d.columns: acc[k] = d[k] if k not in acc else acc[k].add(d[k], fill_value=0.0)
        m = pd.DataFrame({k: v / len(HOURS) for k, v in acc.items()}).sort_index(); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; assert np.allclose(m.r24.values, db.mon_cell_h1(s).reindex(m.index).values, atol=1e-12), s
        d200 = states(s).shift(1).reindex(m.index, method="ffill").sma200.values; m["sym"] = s; m["f"] = np.where(np.isnan(d200), 1.0, np.where(d200 < 0, 1.0, 0.5)); m["vix"] = VIX.reindex(pd.DatetimeIndex(m.index) - pd.Timedelta(days=3), method="ffill").values; rows.append(m)
    P = pd.concat(rows).sort_index(kind="stable"); P["hot"] = (P.vix > TH).fillna(False); return P
def fx_series(P, kind="base"):
    r = {"base": P.r24.values, "L1": np.where(P.hot, P.rN, P.r24), "L2": np.where(P.hot, P.rN, P.r20), "E1": np.where(P.hot, P.r24, P.r20)}[kind]; return pd.Series(r * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
def idx_series(s, kind="base"):
    """指数の月曜(13 UTC 建て・24h)。L = 前金曜 VIX > 25 の週は月曜 20 UTC 建て → 火曜 13 UTC 決済。"""
    b = shot(s, 13, None); b = b[b.index >= PRE0]; n = night(s, 13); n = n[n.dow == 0].r.reindex(b.index); hot = (VIX.reindex(pd.DatetimeIndex(b.index) - pd.Timedelta(days=3), method="ffill").values > TH)
    return b if kind == "base" else pd.Series(np.where(hot & n.notna().values, n.values, b.values), index=b.index)
def short_nights_weekly(syms=("NAS100", "US500"), w_each=0.125):
    out = None
    for s in syms:
        x = night(s, 13); x = x[(x.vix > TH) & (x.dow >= 1)]; c = cost(s, np.ones(len(x))); y = ((-x.r - 2 * c) * w_each).groupby(x.week).sum(); out = y if out is None else out.add(y, fill_value=0.0)   # 買いの損益(コスト後)r = 粗 − c → 売り = −粗 − c = −r − 2c
    return out
def late_entry(kind="L1"):
    """紙上候補用。L1・L2・S1 は index = 月曜(週次)、L3〜L5 は指数名を渡す(例 'NAS100')。"""
    if kind in ("L1", "L2"): return fx_series(fx_frame(), kind)
    if kind == "S1": B = fx_series(fx_frame()); return B.add(short_nights_weekly().reindex(B.index).fillna(0.0), fill_value=0.0)
    return idx_series(kind, "L")
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; P = fx_frame(); B = fx_series(P); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []; parts = []
    def judge(nm, b_, v_, cum_rule=False):
        ok = all(v_[w][0] > b_[w][0] and v_[w][1] >= b_[w][1] for w, _, _ in WIN); cok = (not cum_rule) or bool(v_["IS"][2] >= 0.5 * b_["IS"][2] and v_["OOS"][2] >= 0.5 * b_["OOS"][2])
        rows.append(dict(cell=nm, base_PRE=b_["前窓"], var_PRE=v_["前窓"], base_IS=b_["IS"], var_IS=v_["IS"], base_OOS=b_["OOS"], var_OOS=v_["OOS"], sharpe_up_3win=bool(all(v_[w][0] > b_[w][0] for w, _, _ in WIN)), verdict=("成立" if ok and cok else ("成立だが累積 1/2 未満" if ok else "不成立"))))
    for k, nm in (("L1", "L1 円クロス: VIX > 25 の週は 20 UTC 建てで夜だけ(25 以下は元の 24h)"), ("L2", "L2 円クロス: VIX ≤ 25 は同日 20 UTC 決済・25 超は夜だけ")):
        v = fx_series(P, k); judge(nm, bs, {w: stats(v, a, b) for w, a, b in WIN})
    for s in IDX:
        b = idx_series(s, "base"); v = idx_series(s, "L"); judge(f"L {s}: VIX > 25 の週は 20 UTC 建て → 火曜 13 UTC(25 以下は元の 24h)", {w: stats3(b, a, e) for w, a, e in WIN}, {w: stats3(v, a, e) for w, a, e in WIN}, True)
    sn = short_nights_weekly(); v = B.add(sn.reindex(B.index).fillna(0.0), fill_value=0.0); judge("S1 Mon4 + 火〜木の夜の NAS100・US500 の売り(前日 VIX > 25・合計 0.25)", bs, {w: stats(v, a, b) for w, a, b in WIN})
    D = pd.DataFrame(rows); D.to_csv("results/q238_late_entry_after_high_vix.csv", index=False)
    e1 = fx_series(P, "E1"); ref = pd.DataFrame([dict(variant="参照 E1(VIX ≤ 25 は同日 20 UTC・25 超は 24h)", PRE=stats(e1, *WIN[0][1:]), IS=stats(e1, *WIN[1][1:]), OOS=stats(e1, *WIN[2][1:])), dict(variant="参照 売りのレグ単独(週次・合計 0.25)", PRE=stats(sn.reindex(B.index).fillna(0.0), *WIN[0][1:]), IS=stats(sn.reindex(B.index).fillna(0.0), *WIN[1][1:]), OOS=stats(sn.reindex(B.index).fillna(0.0), *WIN[2][1:]))])
    def add(leg, grp, y, w): parts.append(dict(leg=leg, group=grp, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    for w, a, b in ALLW:
        x = P[(P.index >= a) & (P.index <= b)]
        for gn, m in (("VIX 25 超", x.hot), ("VIX 25 以下", ~x.hot)):
            add("円クロス 4 本: 日中の部分(建て → 20 UTC・コスト込み)", gn, x[m].r20, w); add("円クロス 4 本: 夜だけ(20 UTC → 元の決済・コスト込み)", gn, x[m].rN, w); add("円クロス 4 本: 24 時間(コスト込み)", gn, x[m].r24, w)
        for s in IDX:
            dd = shot(s, 13, 20); dd = dd[(dd.index >= max(a, PRE0)) & (dd.index <= b)]; hv = VIX.reindex(pd.DatetimeIndex(dd.index) - pd.Timedelta(days=3), method="ffill").values > TH
            add(f"{s}: 日中の部分(13 → 20 UTC・コスト込み)", "VIX 25 超", dd[hv], w); add(f"{s}: 日中の部分(13 → 20 UTC・コスト込み)", "VIX 25 以下", dd[~hv], w)
            xn = night(s, 13); xn = xn[(xn.index >= a) & (xn.index <= b) & (xn.vix > TH) & (xn.dow >= 1)]; add(f"{s}: 火〜木の夜の売り(コスト込み)", "VIX 25 超", -xn.r - 2 * cost(s, np.ones(len(xn))), w)
    PT = pd.DataFrame(parts); PT.to_csv("results/q238_late_entry_after_high_vix_parts.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 80)
    print(f"Q238: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %[, 週数])"); print(D.to_string(index=False)); print("\n== 参照 =="); print(ref.to_string(index=False))
    print("\n== 部分ごとの平均 bps (本数)・全期間の t =="); PT["key"] = PT.leg + "｜" + PT.group; order = list(dict.fromkeys(PT.key))
    pv = (PT.pivot(index="key", columns="window", values="mean_bps").reindex(order)[[w[0] for w in ALLW]].astype(str) + " (" + PT.pivot(index="key", columns="window", values="n").reindex(order)[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = PT[PT.window == "全期間"].set_index("key").t.reindex(order).values; print(pv.to_string())
