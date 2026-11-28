# -*- coding: utf-8 -*-
"""docs/244 Q284(2026-11-24 登録「登録実行」・セル 7): 週末の BTC の騰落(Q282 と同じ z)を、ほかの条件と併用する形。対象は月曜の円クロス 4 本。
型(セル 7): (1) 縮小 = z ≥ +1 を 0.5 倍 / z ≥ +2 を 0.5 倍 / z ≥ +1 を 0.5 倍 かつ z ≥ +2 を見送る。(2) 飛びと重ねる = z ≥ +1 かつ 飛び > 0 を見送る / z ≥ +1 かつ 飛び ≥ +1 を見送る(飛びは Q279 と同じ)。
(3) VIX と重ねる = z ≥ +1 かつ 前金曜の VIX ≤ 25 を見送る / z ≥ +2 かつ VIX ≤ 25 を見送る。
口座の物差しと判定は Q278〜Q283 と同じ(FTMO 50k の本口座後・①② の両方で現行を上回る)。照合: 現行 = Q282 の現行(s10 96.34・p10 +69.89)。参照: Q282 の単独の 2 つ(セルに数えない)。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q284_btc_weekend_combined_filters_mon4.py <累積セル数>   出力: results/q284_btc_combined_filters.csv"""
import os, sys
_ARGV = list(sys.argv)
import q278_mon_detail_grid_funded_ranking as m
import q279_weekend_gap_skip_funded as q279
import q282_outside_info_btc_weekend_epu_gpr as q282
np, pd, n3 = m.np, m.pd, m.n3
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 7; items, cap, g = m.norm_items("521100397"); fac = m.make_fac(items, False, 0.5); MULT, PAD = 3.75, 0.01
    n3["paths_fac"] = m.paths_v; m.VAR["v"] = m.BASE; b, _ = m.evaluate(items, g, fac, MULT, PAD); print("現行:", b, flush=True); assert abs(b["s10"] - 96.34) < 0.01 and abs(b["p10"] - 69.89) < 0.01, "Q282 の現行と一致しない"
    Z = q282.sig_btc()[0]; GP, _ = q279.gaps(items); V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); vix = V.set_index("d")["CLOSE"].astype(float).sort_index()
    P = m.paths_v(items, None, fac, m.P0, m.P1); wk = pd.Series({pd.Timestamp(p["d"]): p["fin"] * MULT * 100 for p in P}); WK = pd.DataFrame({"mon_pnl_pct": wk}); WK["z"] = Z.reindex(WK.index); WK["gap"] = GP.reindex(WK.index); WK["vix"] = vix.reindex(WK.index - pd.Timedelta(days=3), method="ffill").values; WK["w1"] = WK.index >= m.PM
    print(f"週の数 {len(WK)}・z あり {int(WK.z.notna().sum())}・飛びあり {int(WK.gap.notna().sum())}・z と飛びの相関 {WK.z.corr(WK.gap):+.2f}・z と VIX の相関 {WK.z.corr(WK.vix):+.2f}")
    up1 = WK.z >= 1; up2 = WK.z >= 2
    # 型 = 週ごとの倍率(1.0 = 現行)
    def fm(d1): s = pd.Series(1.0, index=WK.index); [s.__setitem__(mask[mask].index, v) for mask, v in d1]; return s
    RULES = [("参照", "単独: z ≥ +1 を見送る(Q282)", fm([(up1, 0.0)]), 0), ("参照", "単独: z ≥ +2 を見送る(Q282)", fm([(up2, 0.0)]), 0),
             ("縮小", "z ≥ +1 を 0.5 倍", fm([(up1, 0.5)]), 1), ("縮小", "z ≥ +2 を 0.5 倍", fm([(up2, 0.5)]), 1), ("縮小", "z ≥ +1 を 0.5 倍 かつ z ≥ +2 を見送る", fm([(up1, 0.5), (up2, 0.0)]), 1),
             ("飛びと重ねる", "z ≥ +1 かつ 飛び > 0 を見送る", fm([(up1 & (WK.gap > 0), 0.0)]), 1), ("飛びと重ねる", "z ≥ +1 かつ 飛び ≥ +1 を見送る", fm([(up1 & (WK.gap >= 1), 0.0)]), 1),
             ("VIX と重ねる", "z ≥ +1 かつ VIX ≤ 25 を見送る", fm([(up1 & (WK.vix <= 25), 0.0)]), 1), ("VIX と重ねる", "z ≥ +2 かつ VIX ≤ 25 を見送る", fm([(up2 & (WK.vix <= 25), 0.0)]), 1)]
    rows = [dict(kind="—", rule="現行", n_flag=0, n_w1=0, n_w2=0, mean_flag=np.nan, neg_flag=np.nan, mean_rest=round(float(WK.mon_pnl_pct.mean()), 3), cells=0, verdict="基準", **b)]
    for kind, nm, s, cells in RULES:
        ch = s[s != 1.0]; fc = {k: dict(dd) for k, dd in fac.items()}
        for k in fc:
            for d, v in ch.items(): fc[k][d] = fc[k].get(d, 1.0) * float(v)
        r, _ = m.evaluate(items, g, fc, MULT, PAD); fl = WK[WK.index.isin(ch.index)]; rs = WK[~WK.index.isin(ch.index)]; ok = m.win_ok(r, b, "a") and m.win_ok(r, b, "b")
        rows.append(dict(kind=kind, rule=nm, n_flag=len(fl), n_w1=int(fl.w1.sum()), n_w2=int((~fl.w1).sum()), mean_flag=round(float(fl.mon_pnl_pct.mean()), 3), neg_flag=round(float((fl.mon_pnl_pct < 0).mean()), 2), mean_rest=round(float(rs.mon_pnl_pct.mean()), 3), cells=cells, verdict=("参照" if cells == 0 else ("変更候補" if ok else "現行どおり")), ok_w1=m.win_ok(r, b, "a"), ok_w2=m.win_ok(r, b, "b"), d_p5a=round(r["p5a"] - b["p5a"], 2), d_s5a=round(r["s5a"] - b["s5a"], 2), d_p5b=round(r["p5b"] - b["p5b"], 2), d_s5b=round(r["s5b"] - b["s5b"], 2), **r)); print("done", nm, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q284_btc_combined_filters.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 44)
    print(f"\n== Q284(累積セル {cum} + {N} = {cum + N}・FTMO 50k 本口座後・mean_flag = 該当する週の月曜の平均損益 %(現行の数量)) =="); print(D[["rule", "n_flag", "n_w1", "n_w2", "mean_flag", "neg_flag", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "d_p5a", "d_s5a", "d_p5b", "d_s5b", "ok_w1", "ok_w2", "verdict"]].to_string(index=False))
    print(f"\n判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N} 件")
    # 参照: z ≥ +1 の週を、飛び・VIX で分けた月曜の平均
    x = WK[up1]; print("\nz ≥ +1 の週を分ける(週の数 / 平均 % / 負けた割合):")
    for nm, mk in (("飛び > 0", x.gap > 0), ("飛び ≤ 0", x.gap <= 0), ("飛び ≥ +1", x.gap >= 1), ("VIX ≤ 25", x.vix <= 25), ("VIX > 25", x.vix > 25)): y = x[mk]; print(f"  {nm}: {len(y)} / {y.mon_pnl_pct.mean():+.3f} / {(y.mon_pnl_pct < 0).mean():.2f}")
