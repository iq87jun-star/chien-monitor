# -*- coding: utf-8 -*-
"""2026-11-11 ユーザー「チャレンジ通過に近いものは倍率を下げた方が到達確率は上がりますか/現在位置から倍率を可変させると到達率や失格率は向上しますか」(docs/418・診断・セル 0)。
評価中 5 口座を **現在地**(11/10 21:00 UTC の残高・含み損益込みの有効額)から、週の頭に倍率係数 s(現行倍率比)を決める規則ごとに資金化までを MC する。
 週 = 5 年日次(daily_window(ea_book(評価レグ)))の実在の週を復元抽出(週内の日の並びは保つ)。日次 = max(s × r, −dll)(EA 日次ガードで頭打ち)。
 段階: 2-Step は P1 到達で基準 = その時点の残高・床 = 基準 ×(1−mdd)。1-Step は EOD トレーリング床(min(hwm − mdd, 1.0))。
 2 通りの失格: [G] ガードが必ず効く(床割れのみ) / [S] ガード無しの日次 s×r が規約の日次限度(−5%・1-Step −3%)を超えた日は失格(滑り最悪・上限)。
 規則: 固定 1.0 / 0.75 / 0.5、目標接近で絞る(残り < R0 で s = max(smin, 残り/R0))、床接近で絞る(s = clip(余裕/mdd, smin, 1))、両方。
使い方: cd research && python3 -W ignore queue/dyn_mult_eval_20261111.py   出力: results/dyn_mult_eval_20261111.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, ea_book, daily_window, EA_LEGS = (ns[k] for k in ("cfg", "ea_book", "daily_window", "EA_LEGS")); acc_id = ns["ns"]["acc_id"]
# 現在地(額面比): e = 有効額, hwm = 1-Step の EOD 最高(EA INIT 行 102,813.25)
STATE = {"6104739": dict(e=37_535_714 / 35e6, limit=0.05), "6104736": dict(e=10_348_782 / 10e6, limit=0.05),
         "531466484": dict(e=101_993.37 / 1e5, limit=0.03, hwm=1.0281325), "531343523": dict(e=96_297.04 / 1e5, limit=0.05),
         "14166201": dict(e=102_668.92 / 1e5, limit=0.05)}
N, WMAX = 20000, 156
def taper(R0, smin): return lambda rem, buf, mdd: np.maximum(smin, np.minimum(1.0, rem / R0))
def bufp(smin): return lambda rem, buf, mdd: np.clip(buf / mdd, smin, 1.0)
POL = {"固定 1.0(現行)": lambda rem, buf, mdd: np.ones_like(rem), "固定 0.75": lambda rem, buf, mdd: np.full_like(rem, 0.75), "固定 0.5": lambda rem, buf, mdd: np.full_like(rem, 0.5),
       "目標接近で絞る(残り<2%・下限 0.5)": taper(0.02, 0.5), "目標接近で絞る(残り<2%・下限 0.25)": taper(0.02, 0.25), "目標接近で絞る(残り<4%・下限 0.25)": taper(0.04, 0.25),
       "床接近で絞る(下限 0.5)": bufp(0.5), "床接近で絞る(下限 0.25)": bufp(0.25),
       "両方(残り<2%・床・下限 0.25)": lambda rem, buf, mdd: np.minimum(taper(0.02, 0.25)(rem, buf, mdd), bufp(0.25)(rem, buf, mdd))}
rows = []
for a in cfg["accounts"]:
    aid = acc_id(a["name"])
    if aid not in STATE: continue
    st = STATE[aid]; tg = a["targets"]; mdd, dll = a["mdd"], a["dll"]; trail = a.get("rule") == "ftmo1step"; lim = st["limit"]
    rd = daily_window(ea_book(EA_LEGS[aid]["eval"], a.get("swap_xau_bps_m", 0.0)))
    bd = pd.bdate_range(rd.index.min(), rd.index.max()); r = rd.reindex(bd).fillna(0.0)
    wk = [g.values for _, g in r.groupby(pd.Grouper(freq="W-FRI")) if len(g) == 5 and (g != 0).any()]; W = np.array(wk)
    for pname, pol in POL.items():
        for mode in ("G", "S"):
            rng = np.random.default_rng(11)
            e = np.full(N, st["e"]); basel = np.ones(N); stage = np.zeros(N, int); hwm = np.full(N, st.get("hwm", max(st["e"], 1.0))); done = np.zeros(N, int); t = np.zeros(N, int); t1 = np.zeros(N, int)
            for w in range(1, WMAX + 1):
                act = done == 0
                if not act.any(): break
                tgt = basel * (1 + np.array(tg)[np.minimum(stage, len(tg) - 1)])
                fl = np.minimum(hwm - mdd, 1.0) if trail else basel * (1 - mdd)
                s = pol((tgt - e) / basel, (e - fl) / basel, mdd)
                wr = W[rng.integers(0, len(W), N)]
                for d in range(5):
                    act = done == 0; raw = s * wr[:, d]; ret = np.maximum(raw, -dll)
                    e = np.where(act, e * (1 + ret), e)
                    fl = np.minimum(hwm - mdd, 1.0) if trail else basel * (1 - mdd)
                    fail = act & (e <= fl)
                    if mode == "S": fail |= act & (raw < -lim)
                    done[fail] = -1; t[fail] = w
                    hwm = np.maximum(hwm, e); act = done == 0
                    hit = act & (e >= basel * (1 + np.array(tg)[np.minimum(stage, len(tg) - 1)]))
                    last = hit & (stage == len(tg) - 1); done[last] = 1; t[last] = w
                    nxt = hit & ~last; t1[nxt & (t1 == 0)] = w; stage[nxt] += 1; basel[nxt] = e[nxt]
                # s は週の頭に決める(月曜の建て時点)ので週内は固定
            ok = done == 1
            rows.append(dict(account=a["name"], policy=pname, mode=mode, p_fund=ok.mean(), p_fail=(done == -1).mean(), p_fund_26w=(ok & (t <= 26)).mean(), p_fund_52w=(ok & (t <= 52)).mean(),
                             t_med_w=float(np.median(t[ok])) if ok.any() else np.nan, p_p1=((stage >= 1) | ok).mean() if len(tg) > 1 else ok.mean(), t_p1_med=float(np.median(t1[t1 > 0])) if (t1 > 0).any() else np.nan))
    d = pd.DataFrame([x for x in rows if x["account"] == a["name"]])
    print(f"\n== {a['name']}  現在 {st['e']-1:+.2%}  目標 {tg}  週数 {len(W)}")
    for pn in POL:
        g = d[(d.policy == pn) & (d["mode"] == "G")].iloc[0]; s_ = d[(d.policy == pn) & (d["mode"] == "S")].iloc[0]
        print(f"  {pn:<28s} 資金化 {g.p_fund:5.1%} 失格 {g.p_fail:5.1%} 26週 {g.p_fund_26w:5.1%} 52週 {g.p_fund_52w:5.1%} 中央 {g.t_med_w:4.0f}週 現段階通過 {g.p_p1:5.1%} | 滑り最悪: 資金化 {s_.p_fund:5.1%} 失格 {s_.p_fail:5.1%}")
pd.DataFrame(rows).to_csv("results/dyn_mult_eval_20261111.csv", index=False)
