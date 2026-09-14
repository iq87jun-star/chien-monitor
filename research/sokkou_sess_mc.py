# -*- coding: utf-8 -*-
"""docs/240: Fintokei 速攻プロ(+6% 目標・静的 −3%・日次 −2%・1日利益上限 +3%・残り約 21 営業日)で、
Sess 8 / Sess 8+Mon 4 / Mon 4 を何倍で回すのが「期限内合格確率」最大か。5 日ブロック・ブートストラップ 20,000 本。
ガード近似: 日次 −1.5% で当日打切り(balance ガード)・+2.5% で当日打切り(利益上限)・フロア −2.4% で失格・+5.07%(=現在地からの必要幅)で合格。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db, plusmonth_search_h1 as H
from forward.paper_forward import refresh_live
from sess_top5_portfolio import daily
from ea4_compare import comp, invvol, S8, A0, END
START = float(sys.argv[1]) if len(sys.argv) > 1 else 0.93; TARGET = 6.0; FLOOR = -2.4; DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 21
DAY_LOSS, DAY_GAIN = -1.5, 2.5; N = 20000


def race(daily_r, mult, rng, start=START, days=DAYS, block=5):
    r = np.asarray(daily_r.values, float) * mult; nb = len(r) - block + 1
    starts = rng.integers(0, nb, size=(N, days // block + 2)); paths = r[(starts[:, :, None] + np.arange(block)[None, None, :])].reshape(N, -1)[:, :days]
    paths = np.clip(paths, DAY_LOSS / 100, DAY_GAIN / 100)                       # 当日打切りの近似
    eq = start / 100 + np.cumsum(paths, axis=1) * 1.0                            # 初期残高比の累積(単利近似: 目標も静的基準)
    hit = (eq >= TARGET / 100 * 0.845 + 0.0)                                    # 6% ×(1−0.155)?? → 下で厳密化
    # 厳密: 合格 = eq ≥ 6.0%(初期残高比)、失格 = eq ≤ −2.4%
    win = eq >= TARGET / 100; lose = eq <= FLOOR / 100
    w_first = np.where(win.any(axis=1), win.argmax(axis=1), 10 ** 6); l_first = np.where(lose.any(axis=1), lose.argmax(axis=1), 10 ** 6)
    passed = (w_first < l_first) & (w_first < days); failed = (l_first < w_first) & (l_first < days); timeout = ~(passed | failed)
    dmed = int(np.median(w_first[passed]) + 1) if passed.any() else None
    return dict(pass_pct=round(passed.mean() * 100, 1), fail_pct=round(failed.mean() * 100, 1), timeout_pct=round(timeout.mean() * 100, 1), days_med=dmed,
                end_med=round(float(np.median(eq[:, -1])) * 100, 2), end_p10=round(float(np.percentile(eq[:, -1], 10)) * 100, 2))


def main():
    refresh_live(); rng = np.random.default_rng(7)
    K = [("Mon", "GBPJPY"), ("Mon", "EURJPY"), ("Mon", "AUDJPY"), ("Mon", "USDJPY")]; SA = {k: db.leg_series(*k) for k in K}; cA = comp(SA, invvol(SA, K))
    H.A = pd.Timestamp("2021-09-25")
    for cost in (3, 2):
        SB = {k: daily(sym, h0, span, cost) for k, sym, h0, span in S8}; cB = comp(SB, invvol(SB, [k for k, *_ in S8]))
        idx = cA.index.union(cB.index); a = cA.reindex(idx).fillna(0); b = cB.reindex(idx).fillna(0)
        books = {"Sess8": b, "Sess8+Mon4 50/50": 0.5 * a + 0.5 * b, "Mon4": a}
        for win_lab, w0 in (("全期間 2021-10〜", A0), ("直近12m", END - pd.DateOffset(months=12))):
            print(f"\n=== Sess {cost}pip / ブートストラップ元 {win_lab} / 開始 +{START}% / 残り {DAYS} 営業日 ===")
            for name, c in books.items():
                c = c[(c.index >= w0) & (c.index <= END)]
                line = []
                for m in ([4.8, 8, 10, 12, 15, 20] if name != "Mon4" else [2.5, 4, 6, 8]):
                    r = race(c, m, rng); line.append(f"×{m:<4} 合格 {r['pass_pct']:4.1f}% 失格 {r['fail_pct']:4.1f}% 時間切れ {r['timeout_pct']:4.1f}% (中央 {r['days_med']}日・終値中央 {r['end_med']:+.1f}%)")
                print(f"  {name}"); [print("     " + l) for l in line]


if __name__ == "__main__": main()
