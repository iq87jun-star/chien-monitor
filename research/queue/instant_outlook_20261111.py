# -*- coding: utf-8 -*-
"""2026-11-11 ユーザー「その上での期待収益額とタイミングを教えてください」(FN Instant 11988011・v1.19 配備後・Risk Limit 警告 1 回目の控除込み)。
現在地(残高 20,338.37・床 19,138.37 = EOD 最高残高 − 1,200・額面で頭打ち)から 52 週を MC。週 = 5 年日次(daily_window(ea_book(instG)))の実在の週を復元抽出。
 損益 = 初期残高 20,000 に対する加算(EA のロットは初期残高固定)。日次は max(r, −4%)(EA 残高ガード)。
 停止: 日中 equity ≤ 床 + 200(EA 恒久停止)/ 週末に建玉なしで残高 ≤ 床 + 400(EA の新規停止帯に滞留 = 実質停止)。
 出金: EOD 残高 ≥ 21,000(初期比 +5%)の週に、G = 残高 − max(20,600, 床 + 800) を口座から引く(docs/349 §9f 追記 4)。受取 = 0.7 × G。
       初回サイクルだけ受取上限 = 0.7 ×(残高 − 20,000 − 控除 D)。D = 476.87(Risk)+ 40.82(News)= 517.69。控除分は口座に残る前提(case A)/ 初回出金時に残高から消える前提(case B)。
使い方: cd research && python3 -W ignore queue/instant_outlook_20261111.py   出力: results/instant_outlook_20261111.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, ea_book, daily_window, EA_LEGS = (ns[k] for k in ("cfg", "ea_book", "daily_window", "EA_LEGS"))
aid = "11988011"; legs = EA_LEGS[aid].get("funded") or EA_LEGS[aid]["eval"]
rd = daily_window(ea_book(legs, 0.0)); bd = pd.bdate_range(rd.index.min(), rd.index.max()); r = rd.reindex(bd).fillna(0.0)
W = np.array([g.values for _, g in r.groupby(pd.Grouper(freq="W-FRI")) if len(g) == 5 and (g != 0).any()])
wk = W.sum(1) * 20000
print(f"legs={legs} 週数={len(W)} 週次損益$: 平均 {wk.mean():+.0f} 中央 {np.median(wk):+.0f} σ {wk.std():.0f} 勝率 {(wk>0).mean():.0%}  P(週 ≥ +662)={(wk>=661.63).mean():.1%}")
INIT, BAL0, FL0, D, N, WMAX, JPY = 20000.0, 20338.37, 19138.37, 517.69, 40000, 52, 158.0
rows = []
RUNS = [("A 控除分は口座に残る", 1.0, 800.0), ("A 控除分は口座に残る", 0.95, 800.0), ("B 控除分は初回出金時に残高から消える", 1.0, 800.0),
        ("A 控除分は口座に残る", 1.0, 1000.0), ("A 控除分は口座に残る", 1.0, 1200.0), ("A 控除分は口座に残る", 1.0, 1600.0), ("A 控除分は口座に残る", 1.0, 2000.0), ("A 控除分は口座に残る", 1.0, 1e9)]
# K = 出金後に床の上へ残す額(現行規則 800 = 4%)。1e9 = 出金しない(停止時期の基準)。haircut 0.95 = SL リスク上限(v1.19)で指数レグが縮む週の影響を期待値 −5% と置いた感度
for case, haircut, K in RUNS:
    for _ in (0,):
        rng = np.random.default_rng(7)
        bal = np.full(N, BAL0); fl = np.full(N, FL0); alive = np.ones(N, bool); first = np.zeros(N, int); stopw = np.zeros(N, int)
        recv = np.zeros((N, WMAX + 1)); npay = np.zeros(N, int); cum = np.zeros(N); tier2 = np.zeros(N, int)
        for w in range(1, WMAX + 1):
            wr = W[rng.integers(0, len(W), N)] * haircut
            for d in range(5):
                ret = np.maximum(wr[:, d], -0.04) * INIT
                bal = np.where(alive, bal + ret, bal)
                halt = alive & (bal <= fl + 200); alive &= ~halt; stopw[halt] = w
                fl = np.where(alive, np.minimum(np.maximum(fl, bal - 1200), INIT), fl)     # EOD 追随・額面で頭打ち
            elig = alive & (bal >= INIT * 1.05)
            G = np.where(elig, bal - np.maximum(20600.0, fl + K), 0.0); G = np.maximum(G, 0.0)
            share = 0.7 * G
            cap1 = 0.7 * np.maximum(bal - INIT - D, 0.0)
            share = np.where(first == 0, np.minimum(share, cap1), share); G = share / 0.7
            pay = elig & (share > 0)
            extra = D if case.startswith("B") else 0.0
            bal = np.where(pay, bal - G - np.where(first == 0, extra, 0.0), bal)
            recv[pay, w] = share[pay]; npay[pay] += 1; cum += np.where(pay, share, 0.0)
            first[pay & (first == 0)] = w
            t2 = (cum >= 2000) & (tier2 == 0); tier2[t2] = w
            stuck = alive & (bal <= fl + 400); alive &= ~stuck; stopw[stuck] = w
        c = recv.cumsum(1)
        for h in (4, 13, 26, 52):
            x = c[:, h]
            rows.append(dict(case=case[:1], haircut=haircut, K=K, weeks=h, p_first=((first > 0) & (first <= h)).mean(), p_stop=((stopw > 0) & (stopw <= h)).mean(),
                             p_stop_before_first=((stopw > 0) & (stopw <= h) & ((first == 0) | (first > stopw))).mean(),
                             recv_mean_usd=x.mean(), recv_med_usd=np.median(x), recv_p10=np.quantile(x, .1), recv_p90=np.quantile(x, .9), p_zero=(x == 0).mean(),
                             recv_mean_jpy=x.mean() * JPY, npay_mean=(recv[:, 1:h + 1] > 0).sum(1).mean(), p_tier2=((tier2 > 0) & (tier2 <= h)).mean()))
        f = first[first > 0]
        sw = stopw[stopw > 0]
        print(f"[{case} / haircut {haircut} / K {K:.0f}] 初回出金: 到達 {len(f)/N:.0%}・中央 {(np.median(f) if len(f) else float('nan')):.0f} 週 / 停止: 52 週内 {(stopw>0).mean():.0%}・中央 {np.median(sw):.0f} 週 / 停止時の残高中央 {np.median(bal[stopw>0]):,.0f}")
out = pd.DataFrame(rows); out.to_csv("results/instant_outlook_20261111.csv", index=False)
pd.set_option("display.width", 250)
print(out.round(3).to_string(index=False))
