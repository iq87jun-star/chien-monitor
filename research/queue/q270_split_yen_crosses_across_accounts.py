# -*- coding: utf-8 -*-
"""docs/244 Q270(2026-11-18 登録「登録実行」・診断・セル 0): 口座ごとに持つ円クロスを分ける。
全口座の同時シミュレーション(forward/portfolio_sim・同じ相場経路・共通の乱数)で、月曜の円クロス 4 本を等分に持つ口座(mon4)を 2 通貨ずつに分けた設計を現行と比べる。
A 組 = GBPJPY + EURJPY、B 組 = AUDJPY + USDJPY。各口座の月曜の名目の合計は変えない(mon4 の倍率 m → 2 通貨 × m/2)。
S1: FTMO 0397 = A・FTMO 7058 = B・宝くじ = A・トパーズ = B・1-Step の mon4 部分 = B・FN 6201(本口座後)= A。S2 = S1 の A と B を入れ替え。
ルビー・パール・FN 4882・Instant は変えない。評価中も本口座後も同じ組。
変更候補の条件: S1・S2 の両方で (1) 期待が現行の −2% 以内 (2) 0 になる確率が 2pt 以上下がる または −1σ が上がる (3) どの口座も評価中の失格が +2pt を超えて増えない。
同時に傷む度合いを数えるため、run_portfolio の本体に「失格した日」を記録する 2 行を足した写しを使う(計算は同じ・portfolio_sim.py は変更しない)。
使い方: cd research && python3 -W ignore queue/q270_split_yen_crosses_across_accounts.py [N]   出力: results/q270_split_currencies.csv・_accounts.csv"""
import os, sys, json, copy, inspect
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
import forward.portfolio_sim as ps
import numpy as np, pandas as pd
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000; SEED = 20261118
_src = inspect.getsource(ps.run_portfolio)
def _rep(s, old, new): assert s.count(old) == 1, old; return s.replace(old, new)
_src = _rep(_src, "ro = np.zeros(N); fund_day = np.full(N, -1); fund_day[funded] = 0", "ro = np.zeros(N); fund_day = np.full(N, -1); fund_day[funded] = 0; failday = np.full(N, -1)")
_src = _rep(_src, "failed |= act & (e <= fl)", "failed |= act & (e <= fl); failday = np.where((failday < 0) & failed, t, failday)")
_src = _rep(_src, "ff = funded & failed", "ff = funded & failed; FAILDAY[a[\"name\"]] = (failday.copy(), funded.copy())")
FAILDAY = {}; ps.FAILDAY = FAILDAY; exec(compile(_src.replace("def run_portfolio(", "def run_portfolio_fd("), "q270_run", "exec"), ps.__dict__)
A = ("mon_gbpjpy", "mon_eurjpy"); Bp = ("mon_audjpy", "mon_usdjpy")
ASSIGN = {"FTMO 50k 521100397": A, "FTMO 50k 531407058": Bp, "宝くじ 531343523": A, "トパーズ 6104739": Bp, "1-Step 531466484": Bp, "FN 14166201": A}
def split(cfg, flip=False):
    c = copy.deepcopy(cfg)
    for a in c["accounts"]:
        if a["name"] not in ASSIGN: continue
        pair = ASSIGN[a["name"]]; pair = (Bp if pair is A else A) if flip else pair
        for key in ("eval", "funded"):
            if "mon4" in a[key]: m = a[key].pop("mon4"); a[key][pair[0]] = a[key].get(pair[0], 0.0) + m / 2; a[key][pair[1]] = a[key].get(pair[1], 0.0) + m / 2
    return c
def joint(fd):
    names = list(fd); D = np.stack([fd[n][0] for n in names], axis=1); nfail = (D >= 0).sum(axis=1); wk = np.where(D >= 0, D // 5, -1 - np.arange(D.shape[1])[None, :])
    same3 = np.array([max(np.unique(r[r >= 0], return_counts=True)[1].max() if (r >= 0).any() else 0, 0) for r in wk])   # 同じ 5 営業日に失格した口座数の最大
    ev = np.stack([(fd[n][0] >= 0) & ~fd[n][1] for n in names], axis=1)                                                     # 評価中に失格
    return dict(失格口座数の平均=round(float(nfail.mean()), 2), 失格5口座以上=round(float((nfail >= 5).mean()) * 100, 1), 同じ週に2口座以上=round(float((same3 >= 2).mean()) * 100, 1), 同じ週に3口座以上=round(float((same3 >= 3).mean()) * 100, 1), 同じ週に4口座以上=round(float((same3 >= 4).mean()) * 100, 1), 評価中の失格口座数の平均=round(float(ev.sum(axis=1).mean()), 2))
if __name__ == "__main__":
    cfg = json.load(open("config/portfolio_current.json", encoding="utf-8")); rows = []; acc = []; S = {}
    for nm, c in (("現行", cfg), ("S1", split(cfg)), ("S2(入れ替え)", split(cfg, True))):
        FAILDAY.clear(); res = ps.run_portfolio_fd(c, N=N, seed=SEED); s = ps.summarize(res, nm); j = joint(dict(FAILDAY)); S[nm] = (s, res["stats"])
        rows.append(dict(設計=nm, 期待=round(s["mean"], 1), 下1σ=round(s["p16"], 1), 中央=round(s["p50"], 1), 上1σ=round(s["p84"], 1), ゼロの確率=round(s["p0"] * 100, 1), 月30万未満=round(s["p30"] * 100, 1), **j))
        for a, st in res["stats"].items(): acc.append(dict(設計=nm, 口座=a, 到達=round(st["reach"] * 100, 1), 評価中の失格=round(st["fail_eval"] * 100, 1), 本口座後の失格=round(st["fail_funded"] * 100, 1), 期待_万円=round(float(res["per"][a][0].mean()) / 1e4, 1)))
        print("done", nm, flush=True)
    D = pd.DataFrame(rows); AC = pd.DataFrame(acc); D.to_csv("results/q270_split_currencies.csv", index=False); AC.to_csv("results/q270_split_currencies_accounts.csv", index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 100); print(f"\n== Q270(N={N}・乱数種 {SEED}) =="); print(D.to_string(index=False))
    P = AC.pivot(index="口座", columns="設計"); print(P[["到達", "評価中の失格", "本口座後の失格", "期待_万円"]].to_string())
    b, bst = S["現行"]; ok = {}
    for nm in ("S1", "S2(入れ替え)"):
        s, st = S[nm]; c1 = s["mean"] >= b["mean"] * 0.98; c2 = (s["p0"] <= b["p0"] - 0.02) or (s["p16"] > b["p16"]); worst = max(st[a]["fail_eval"] - bst[a]["fail_eval"] for a in st); c3 = worst <= 0.02
        ok[nm] = c1 and c2 and c3; print(f"{nm}: (1) 期待 {b['mean']:.1f} → {s['mean']:.1f} = {c1}・(2) 0 の確率 {b['p0']*100:.1f} → {s['p0']*100:.1f}% / −1σ {b['p16']:.1f} → {s['p16']:.1f} = {c2}・(3) 評価中の失格の最大の増加 {worst*100:+.1f}pt = {c3} → {'満たす' if ok[nm] else '満たさない'}")
    print("判定:", "変更候補(口座ごとの精密な再現へ)" if all(ok.values()) else "現行どおり")
    # 参考: 2 組の月曜の系列の関係
    lg = ps.legs(); a_ = (lg["mon_gbpjpy"] + lg["mon_eurjpy"]) / 2; b_ = (lg["mon_audjpy"] + lg["mon_usdjpy"]) / 2; m = (a_ != 0) | (b_ != 0); x = pd.DataFrame({"A": a_[m], "B": b_[m], "M4": lg["mon4"][m]})
    print("\n参考(月曜の建玉がある日): 相関 A×B", round(x.A.corr(x.B), 3), "・日次の標準偏差 A", round(x.A.std() * 1e4, 1), "B", round(x.B.std() * 1e4, 1), "4 本", round(x.M4.std() * 1e4, 1), "bps・平均 A", round(x.A.mean() * 1e4, 2), "B", round(x.B.mean() * 1e4, 2), "4 本", round(x.M4.mean() * 1e4, 2))
    q10 = x.M4.quantile(0.1); print("4 本の悪い 1 割の日: A", round(x.A[x.M4 <= q10].mean() * 1e4, 1), "B", round(x.B[x.M4 <= q10].mean() * 1e4, 1), "4 本", round(x.M4[x.M4 <= q10].mean() * 1e4, 1), "bps")
