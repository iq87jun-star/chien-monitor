# -*- coding: utf-8 -*-
"""docs/244 Q272(2026-11-20 登録「登録実行」・セル 12): 1-Step の保有枠を金以外(UK100・原油)にする。
ユーザー 2026-11-20「金以外で採用可能なものはありますか」。Q190(docs/430)の候補「Hold UK100 0.31 / WTI 0.10」は、スワップの費用と含み損の持ち越しを入れていなかった。
口座モデル・開始状態は Q271 と同じ(残高 −2.17%・EOD の最高 +2.81%・11 月の発動 2 回・月内の停止は EA どおり 3 回目・2026-11-23 からの暦・52 週)。
型: A = 金の代わりに UK100 0.31 + 原油 0.10 / B = 金 半分 0.18 + UK100 0.31 + 原油 0.10。
スワップ(UK100・原油の買い持ち・実測なし): 年 0%・−5%・−8%。金は月 −52 bps。
場面: 実績のまま / 横ばい(保有する全銘柄を年率 0% に)。参照: 下落(全銘柄 年率 −6%)。
保有の表し方: 銘柄を重みで束ねた日次の指数(毎日重みを戻す近似)を 1 本の保有として Q253 の episode に入れる。安値は各銘柄の安値が同時に付いたと置く(保守的)。
価格: UK100・原油 = Dukascopy の日足(〜2025-12)+ 2026 年分は Yahoo(data_live)の日次の騰落でつなぐ。金 = data/XAUUSD_rf.csv(従来どおり)。暦は金の日足にそろえる。
判定 = Q233 の ev_ok(基準 = その場面の現状 = 金 0.36 倍)。提案に進めるのはスワップ −8% で実績・横ばいの両方で変更候補の型だけ。
照合: 金だけの束(0.36 倍)で Q271 の「現状」の行(実績 92.9 / 7.1・30.6 / 55.1、横ばい 76.2 / 15.7・29.6 / 63.3)を再現する。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q272_one_step_hold_uk100_oil_instead_of_gold.py <累積セル数>   出力: results/q272_one_step_hold_basket.csv"""
import os, sys
_ARGV = list(sys.argv)
import q271_one_step_gold_from_current_state as q1
np, pd, n5, GA, run, ML, STARTS, g, ev_ok = q1.np, q1.pd, q1.n5, q1.GA, q1.run, q1.ML, q1.STARTS, q1.g, q1.ev_ok
DG0 = q1.DG0; P0, P1, PM = q1.P0, q1.P1, q1.PM; CAL = DG0.index; START, HWM = q1.START, q1.HWM
def load_spliced(sym):
    """Dukascopy の日足(〜2025-12)に、2026 年分を data_live(Yahoo)の日次の騰落でつなぐ。金の暦にそろえる。"""
    k = pd.read_csv(f"data_dukascopy/{sym}_day.csv"); k["d"] = pd.to_datetime(k["timestamp"]).dt.normalize(); k = k.drop_duplicates("d", keep="last").set_index("d").sort_index()[["open", "high", "low", "close"]]
    k = k[(k["close"] > 0) & (k.index.dayofweek < 5)]
    l = pd.read_csv(f"data_live/{sym}_rf.csv"); l["d"] = pd.to_datetime(l["timestamp"]).dt.normalize(); l = l.drop_duplicates("d", keep="last").set_index("d").sort_index()[["open", "high", "low", "close"]]
    cut = k.index[-1]; base = l["close"][:cut]; assert len(base) and (l["close"][cut:] > 0).all(), sym
    ratio = float(k["close"].iloc[-1]) / float(base.iloc[-1]); tail = l[l.index > cut] * ratio
    D = pd.concat([k, tail]).sort_index(); c = D["close"].reindex(CAL, method="ffill"); lo = D["low"].reindex(CAL); lo = lo.fillna(c).clip(upper=c.where(lo.isna(), np.inf))
    return pd.DataFrame({"close": c, "low": np.minimum(lo, c)}), int(len(tail)), cut
def detrend(D, drift):
    """Q254 と同じ: 2 期間それぞれの対数収益の平均を引いて、年率の傾きを足す。安値は終値との比を保つ。"""
    if drift is None: return D.copy()
    lr = np.log(D["close"]).diff().fillna(0.0); adj = lr.copy()
    for a, b in ((P0 - pd.Timedelta(days=30), PM - pd.Timedelta(days=1)), (PM, P1 + pd.Timedelta(days=7))):
        m = (D.index >= a) & (D.index <= b); adj[m] = lr[m] - lr[m].mean() + drift / 252.0
    c = float(D["close"].iloc[0]) * np.exp(adj.cumsum()); return pd.DataFrame({"close": c, "low": D["low"] * (c / D["close"])})
def basket(parts):
    """parts = [(日足, 重み)]。毎日重みを戻す束の指数(終値・安値)。安値は各銘柄の安値が同時に付いたと置く。"""
    Wt = sum(w for _, w in parts); rc = 0.0; rl = 0.0
    for D, w in parts:
        pc = D["close"].shift(1); rc = rc + (w / Wt) * (D["close"] / pc - 1).fillna(0.0); rl = rl + (w / Wt) * (D["low"] / pc - 1).fillna(0.0)
    c = 100.0 * (1 + rc).cumprod(); lo = c.shift(1).fillna(100.0) * (1 + rl)
    return pd.DataFrame({"open": c.shift(1).fillna(100.0), "high": c, "low": np.minimum(lo, c), "close": c}, index=CAL)
def one(Wt, swm, start=START):
    kw = dict(start=start, target=0.10, mdd=0.10, pad=0.01, smin=None, trail=True, g=g, swm=swm, wg0=Wt, carry0=0.0, wg_re=Wt, integ=True); r = {}
    for wn in ("W1", "W2"):
        o = run(ML, STARTS[wn], "A", **kw); r[f"reach_{wn}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{wn}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{wn}"] = max(o[t]["weeks"] for t in o); r[f"fires_{wn}"] = round(max(o[t]["fires_per52"] for t in o), 2); r[f"hold_only_{wn}"] = round(max(o[t]["gold_only"] for t in o), 2)
    return r
def use(parts):
    n5["DG"] = basket(parts); GA["A"] = n5["gold_arrays"]("A")
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 12; rows = []
    GOLD = pd.DataFrame({"close": DG0["close"], "low": np.minimum(DG0["low"], DG0["close"])}); UK, nuk, cuk = load_spliced("UK100"); OIL, noil, coil = load_spliced("WTI")
    print(f"価格: UK100 Dukascopy 〜{cuk.date()} + Yahoo {nuk} 日 / 原油 Dukascopy 〜{coil.date()} + Yahoo {noil} 日。", {s: [round(float(D['close'][:t].iloc[-1]), 1) for t in ('2016-11-01', '2021-07-31', '2026-07-31')] for s, D in (('金', GOLD), ('UK100', UK), ('原油', OIL))}, flush=True)
    c3 = pd.concat([np.log(D["close"]).diff() for D in (GOLD, UK, OIL)], axis=1).dropna(); c3.columns = ["金", "UK100", "原油"]; print("日次の相関:", c3.corr().round(2).to_dict(), "・日次の標準偏差 %:", (c3.std() * 100).round(2).to_dict(), flush=True)
    q1.setup(HWM, 2, 3, True); SG = -52.0; WG, WU, WO = 0.36, 0.31, 0.10
    SC = [("実績のまま", None, True), ("横ばい(年率 0%)", 0.0, True), ("参照: 下落(年率 −6%)", float(np.log(1 - 0.06)), False)]
    for sn, dr, judged in SC:
        G_, U_, O_ = detrend(GOLD, dr), detrend(UK, dr), detrend(OIL, dr)
        use([(G_, WG)]); b = one(WG, SG); rows.append(dict(part="基準", scenario=sn, variant="現状(金 0.36 倍)", swap="金 −52 bps/月", cells=0, **b))
        use([(G_, WG / 2)]); rows.append(dict(part="参照", scenario=sn, variant="金 半分(0.18 倍)", swap="金 −52 bps/月", cells=0, **one(WG / 2, SG)))
        rows.append(dict(part="参照", scenario=sn, variant="金なし", swap="—", cells=0, **one(0.0, 0.0)))
        for sy in (0.0, -0.05, -0.08):
            sm = sy / 12 * 1e4
            use([(U_, WU), (O_, WO)]); rows.append(dict(part="判定" if judged else "参照", scenario=sn, variant="A 金の代わりに UK100 0.31 + 原油 0.10", swap=f"年 {sy * 100:.0f}%", cells=1 if judged else 0, **one(WU + WO, sm)))
            use([(G_, WG / 2), (U_, WU), (O_, WO)]); wb = WG / 2 + WU + WO; rows.append(dict(part="判定" if judged else "参照", scenario=sn, variant="B 金 半分 + UK100 0.31 + 原油 0.10", swap=f"年 {sy * 100:.0f}%", cells=1 if judged else 0, **one(wb, (WG / 2 * SG + (WU + WO) * sm) / wb)))
        for nm, parts, wt in (("参照: UK100 0.31 だけ", [(U_, WU)], WU), ("参照: 原油 0.10 だけ", [(O_, WO)], WO)):
            use(parts); rows.append(dict(part="参照", scenario=sn, variant=nm, swap="年 -5%", cells=0, **one(wt, -0.05 / 12 * 1e4)))
        print("done", sn, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q272_one_step_hold_basket.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
    print(f"\n== Q272(累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False))
    print("\n照合(Q271 の現状: 実績 92.9 / 7.1・30.6 / 55.1、横ばい 76.2 / 15.7・29.6 / 63.3):", [(r.scenario, r.reach_W1, r.fail_W1, r.reach_W2, r.fail_W2) for _, r in D[D.part == "基準"].iterrows()])
    print("\n== 判定(基準 = その場面の現状 = 金 0.36 倍)・参照: 金 半分 / 金なし に対して ==")
    for sn, x in D.groupby("scenario", sort=False):
        b = x[x.part == "基準"].iloc[0]; h = x[x.variant.str.startswith("金 半分")].iloc[0]; z = x[x.variant == "金なし"].iloc[0]
        for _, v in x[x.variant.str.startswith(("A ", "B "))].iterrows():
            print(f"  [{v.part}・{sn}] {v.variant}・{v.swap} → {'変更候補' if ev_ok(b, v) else '現行どおり'}(到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}% vs {b.reach_W1:.0f} / {b.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}% vs {b.fail_W1:.0f} / {b.fail_W2:.0f}%・週 {v.weeks_W1} / {v.weeks_W2})| 金 半分 に対して {'上回る' if ev_ok(h, v) else '上回らない'}・金なし に対して {'上回る' if ev_ok(z, v) else '上回らない'}")
    for nm in ("A ", "B "):
        x = D[(D.part == "判定") & D.variant.str.startswith(nm) & (D.swap == "年 -8%")]; ok = all(ev_ok(D[(D.part == "基準") & (D.scenario == r.scenario)].iloc[0], r) for _, r in x.iterrows())
        print(f"提案に進める条件(スワップ −8% で実績・横ばいの両方が変更候補)・{nm.strip()}: {'満たす' if ok else '満たさない'}")
