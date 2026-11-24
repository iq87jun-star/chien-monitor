# -*- coding: utf-8 -*-
"""docs/244 Q279(2026-11-24 登録「登録して実行」・セル 6): 週明けの始値の飛びで月曜の円クロスを見送る形(要人の発言の「代わりの物差し」・docs/519)。
飛び = 円クロス 4 本それぞれの(月曜 04:00 UTC の始値 − 金曜の最後の終値)÷ ATR24(月曜 04:00 時点)を、月曜の枠の重みで平均。
型(セル 6): 見送る条件 = 飛び ≤ −2 / ≤ −3、飛び ≥ +2 / ≥ +3、|飛び| ≥ 2 / ≥ 3。口座の物差しと判定は Q278 と同じ(FTMO 50k の本口座後・両方の期間で現行を上回る)。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q279_weekend_gap_skip_funded.py <累積セル数>   出力: results/q279_weekend_gap_skip.csv・results/q279_weekend_gap_weeks.csv"""
import os, sys
_ARGV = list(sys.argv)
import q278_mon_detail_grid_funded_ranking as m
np, pd, q, n3 = m.np, m.pd, m.q, m.n3
RULES = (("下に飛んだ週 ≤ −2", lambda g: g <= -2), ("下に飛んだ週 ≤ −3", lambda g: g <= -3), ("上に飛んだ週 ≥ +2", lambda g: g >= 2), ("上に飛んだ週 ≥ +3", lambda g: g >= 3), ("どちらでも |飛び| ≥ 2", lambda g: abs(g) >= 2), ("どちらでも |飛び| ≥ 3", lambda g: abs(g) >= 3))
def gaps(items):
    per = {}
    for s, idxf, w in items:
        df = q.load(s); atr = q.atr24(df); cl = df["close"]; out = {}
        for d in pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))):
            t = d + pd.Timedelta(hours=4)
            if t not in df.index: continue
            a = atr.get(t, np.nan); prev = cl[:d - pd.Timedelta(days=1)]
            if a != a or a <= 0 or len(prev) == 0: continue
            out[d] = (float(df["open"][t]) - float(prev.iloc[-1])) / float(a)
        per[s] = pd.Series(out)
    G = pd.DataFrame(per).dropna(); wts = np.array([w for s, i, w in items]); return (G * wts).sum(axis=1) / wts.sum(), G
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; items, cap, g = m.norm_items("521100397"); fac = m.make_fac(items, False, 0.5); MULT, PAD = 3.75, 0.01
    n3["paths_fac"] = m.paths_v; m.VAR["v"] = m.BASE; b, Tb = m.evaluate(items, g, fac, MULT, PAD); print("現行:", b, flush=True)
    GP, per = gaps(items); GP = GP[(GP.index >= m.P0) & (GP.index <= m.P1)]
    print(f"飛び(ATR24 の倍数・{len(GP)} 週): 平均 {GP.mean():+.2f}・標準偏差 {GP.std():.2f}・分位 1% {GP.quantile(.01):+.2f} / 5% {GP.quantile(.05):+.2f} / 25% {GP.quantile(.25):+.2f} / 50% {GP.quantile(.5):+.2f} / 75% {GP.quantile(.75):+.2f} / 95% {GP.quantile(.95):+.2f} / 99% {GP.quantile(.99):+.2f}", flush=True)
    # 週ごとの月曜の損益(本口座後の構成・数量 1.0 の段階・ガード後・終値判定)
    P = m.paths_v(items, None, fac, m.P0, m.P1); wk = pd.Series({pd.Timestamp(p["d"]): p["fin"] * MULT for p in P}); WK = pd.DataFrame({"gap": GP, "mon_pnl_pct": wk * 100}).dropna(); WK["w1"] = WK.index >= m.PM
    WK.to_csv("results/q279_weekend_gap_weeks.csv"); print(f"飛びと月曜の損益の相関: 全期間 {WK.gap.corr(WK.mon_pnl_pct):+.2f}・① {WK[WK.w1].gap.corr(WK[WK.w1].mon_pnl_pct):+.2f}・② {WK[~WK.w1].gap.corr(WK[~WK.w1].mon_pnl_pct):+.2f}")
    print("飛びの帯ごとの月曜の平均損益 %(本口座後の数量・ガード前):"); bins = [-99, -3, -2, -1, 0, 1, 2, 3, 99]; WK["band"] = pd.cut(WK.gap, bins); print(WK.groupby("band", observed=True).agg(n=("gap", "size"), mean=("mon_pnl_pct", "mean"), neg_share=("mon_pnl_pct", lambda x: float((x < 0).mean())), n_w1=("w1", "sum")).round(3).to_string())
    rows = [dict(rule="現行(見送りなし)", n_skip=0, n_skip_w1=0, n_skip_w2=0, mean_skip=np.nan, mean_keep=round(float(WK.mon_pnl_pct.mean()), 3), cells=0, verdict="基準", **b)]
    for nm, fn in RULES:
        flag = {d for d, x in GP.items() if fn(x)}; fc = {k: {d: (0.0 if d in flag else v) for d, v in dd.items()} for k, dd in fac.items()}
        for k in fc:
            for d in flag: fc[k].setdefault(d, 0.0)
        r, _ = m.evaluate(items, g, fc, MULT, PAD); sk = WK[WK.index.isin(flag)]; kp = WK[~WK.index.isin(flag)]; ok = m.win_ok(r, b, "a") and m.win_ok(r, b, "b")
        rows.append(dict(rule=nm, n_skip=len(sk), n_skip_w1=int(sk.w1.sum()), n_skip_w2=int((~sk.w1).sum()), mean_skip=round(float(sk.mon_pnl_pct.mean()), 3) if len(sk) else np.nan, mean_keep=round(float(kp.mon_pnl_pct.mean()), 3), cells=1, verdict="変更候補" if ok else "現行どおり", ok_w1=m.win_ok(r, b, "a"), ok_w2=m.win_ok(r, b, "b"), **r)); print("done", nm, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q279_weekend_gap_skip.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40)
    print(f"\n== Q279(累積セル {cum} + {N} = {cum + N}・FTMO 50k 本口座後・mean_skip / mean_keep = 見送る週 / 残す週の月曜の平均損益 %) =="); print(D[["rule", "n_skip", "n_skip_w1", "n_skip_w2", "mean_skip", "mean_keep", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "ok_w1", "ok_w2", "verdict"]].to_string(index=False))
    print(f"\n判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N} 件")
