# -*- coding: utf-8 -*-
"""docs/244 Q291(2026-11-26 登録「登録実行」・毎日の作案 I-2・セル 18): 11 月の購入候補(docs/383 Q88 の 9 候補)を、いまのガードを入れて出し直す。
枠組みは Q88 と同じ(日次の帳簿・5 日ブロック・6,000 本・36 か月)。型: G0 = ガードなし / G2 = 月曜の円クロスに 200 日線(線より上は 0.5 倍)+ 損失枠の縮小(× clamp(床までの余裕 ÷ 損失枠, 0.5, 1))/ G3 = G2 + SKEW の見送り。
指数・金・GER40 には掛けない。期間は 200 日線の状態が使える 2016-11-01〜2026-07-29 に 3 つの型をそろえる(全期間の G0 は Q88 の再現確認だけ)。
判定(候補 × {G2, G3}): G0 に対して 改善 = 純益 ≥ G0 かつ 失格 ≤ G0 + 1 で(純益 +10% 以上 or 失格 −3 以上)/ 悪化 = 純益 −10% 超 or 失格 +3 超 / それ以外 差なし。
まとめ: 候補ごとに悪化でない型の中で純益最大(無ければ G0)を採って順位付け。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q291_purchase_mc_with_current_guards.py <累積セル数>   出力: results/q291_purchase_mc_guards.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
# ---- 1) 口座モデルの前半から、通貨ごとの 200 日線の状態と SKEW の分位を取る(Q286 と同じ定義) ----
_s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)
n3 = n["n3"]; PAIRS = ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY"); WEAK = {s: dict(n3["flags_of"](s)) for s in PAIRS}; PRK = n3["PRK"]
# ---- 2) Q88 の枠組み(simulate・CANDS・帳簿)を読む ----
_q = open(os.path.join(HERE, "q88_purchase_mc_2026-11.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]; q88 = {"__name__": "q88_head", "__file__": os.path.join(HERE, "q88_purchase_mc_2026-11.py")}; sys.argv = sys.argv[:1]; exec(compile(_q, "q88_head", "exec"), q88)
np, pd, legs, book, L, simulate, CANDS, FX, N, BLOCK, MONTHS, DAYS, SEED, P1 = (q88[k] for k in ("np", "pd", "legs", "book", "L", "simulate", "CANDS", "FX", "N", "BLOCK", "MONTHS", "DAYS", "SEED", "P1"))
PC = pd.Timestamp("2016-11-01"); LM = {s: L("Mon", s) for s in PAIRS}; lg = legs()
def fac_series(s, skew):
    """月曜ごとの係数: 200 日線より上 0.5・下 1.0(状態が無い週は 1.0)。skew=True なら前金曜の SKEW 分位 > 0.8 の月曜は 0。"""
    x = LM[s]; d = x.index; pr = PRK.reindex(d - pd.Timedelta(days=3), method="ffill").values; f = np.array([(1.0 if WEAK[s].get(t, True) else 0.5) for t in d])
    if skew: f = np.where((pr == pr) & (pr > 0.8), 0.0, f)
    return pd.Series(f, index=d)
F = {"G0": {s: 1.0 for s in PAIRS}, "G2": {s: fac_series(s, False) for s in PAIRS}, "G3": {s: fac_series(s, True) for s in PAIRS}}
def split(spec, G):
    mon = lg["mon4"] * 0.0; oth = lg["mon4"] * 0.0
    for k, w in spec.items():
        if k == "mon4": mon = mon + w * sum(LM[s] * F[G][s] * 0.25 for s in PAIRS)
        elif k == "a9": mon = mon + w * LM["GBPJPY"] * F[G]["GBPJPY"] / 3; oth = oth + w * (lg["holdxau"] + lg["nas"]) / 3
        else: oth = oth + w * lg[k]
    return mon, oth
def Rr(c, p0): return np.asarray(c[(c.index >= p0) & (c.index <= P1)].values, float)
def simulate3(c, G, shrink, p0, bestday_gate=None):
    """Q88 の simulate と同じ。月曜の円クロスの部分だけに係数(G)と損失枠の縮小(shrink)を掛ける。G0・shrink=False・p0 = 全期間なら simulate と一致する。"""
    em, eo = split(c["eval"], G); fm, fo = split(c["funded"], G); rng = np.random.default_rng(SEED); T = len(Rr(em, p0)); nb = T - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    cem, ceo, cfm, cfo = (Rr(x, p0)[IDX] for x in (em, eo, fm, fo)); tg = c["targets"]; mdd = c["mdd"]; dll = c["dll"]; bal = c["balance_jpy"]; kk = c["k"]; kp = c["keep"]; pf = c["pay_frac"]; sp = c["split"]; trail = c.get("trail", False)
    e = np.ones(N); basel = np.ones(N); stage = np.zeros(N, int); funded = np.zeros(N, bool); failed = np.zeros(N, bool); hwm = np.ones(N); reach_day = np.full(N, 10**6); paid = np.zeros((N, MONTHS)); cum_since = np.zeros(N); best_since = np.zeros(N); gate_skips = 0; ssum = 0.0; scnt = 0
    for t in range(DAYS):
        act = ~failed; fl = np.minimum(hwm - mdd, 1.0) if trail else basel * (1 - mdd)
        f = np.where(funded, np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk), 1.0); sh = np.clip((e - fl) / (basel * mdd), 0.5, 1.0) if shrink else 1.0
        ret = np.clip(np.where(funded, (cfm[:, t] * sh + cfo[:, t]) * f, cem[:, t] * sh + ceo[:, t]), -dll, None)
        e_prev = e.copy(); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
        d = np.where(act & funded, e - e_prev, 0.0); cum_since += d; best_since = np.maximum(best_since, d)
        for s in range(len(tg)):
            hit = act & ~failed & ~funded & (stage == s) & (e >= basel * (1 + tg[s]))
            if s == len(tg) - 1: funded |= hit; reach_day[hit] = t + 1; e[hit] = 1.0; basel[hit] = 1.0; hwm[hit] = 1.0
            else: stage[hit] = s + 1; basel[hit] = e[hit]
        if (t + 1) % 21 == 0:
            m = (t + 1) // 21 - 1; w = np.where(funded & ~failed, np.maximum(e - basel * (1 + kp), 0.0) * pf, 0.0)
            if bestday_gate is not None:
                blocked = (w > 0) & (best_since > bestday_gate * np.maximum(cum_since, 1e-9)); gate_skips += int(blocked.sum()); w = np.where(blocked, 0.0, w)
            paid[:, m] = w * bal * sp; e -= w; pay = w > 0; cum_since[pay] = 0.0; best_since[pay] = 0.0
    rd = reach_day[funded]; p36 = paid.sum(1); steady = []
    for i in np.flatnonzero(funded):
        m0 = int(reach_day[i] // 21) + 12
        if m0 + 12 <= MONTHS: steady.append(paid[i, m0:m0 + 12].mean())
    return dict(reach=funded.mean() * 100, fail=failed.mean() * 100, fail_eval=(failed & ~funded).mean() * 100, fail_funded=(failed & funded).mean() * 100, reach_med_days=(float(np.median(rd)) if len(rd) else None), pay36=p36.mean() / 1e4, pay36_p0=(p36 <= 0).mean() * 100, steady_m=(float(np.mean(steady)) / 1e4 if steady else 0.0))
if __name__ == "__main__":
    cum = int(_ARGV[1]); NC = 18; rows = []; P0full = pd.Timestamp("2016-01-04")
    for G in ("G2", "G3"):
        x = sum(F[G][s][(F[G][s].index >= PC) & (LM[s] != 0)] for s in PAIRS) / 4; print(f"[{G}] 月曜の円クロスの係数の平均(2016-11〜): {x.mean():.3f}・0 の週 {100 * (x == 0).mean():.1f}%", flush=True)
    for nm, c, fee_usd, n_acc, note in CANDS:
        gate = 0.40 if nm.startswith("E8") else None; fee = fee_usd * FX * n_acc / 1e4; r88 = simulate(c, bestday_gate=gate); chk = simulate3(c, "G0", False, P0full, gate)
        assert abs(r88["reach"] - chk["reach"]) < 1e-9 and abs(r88["fail"] - chk["fail"]) < 1e-9 and abs(r88["pay36"] - chk["pay36"]) < 1e-6, (nm, r88, chk)
        res = {"Q88 再現(全期間・G0)": chk, "G0": simulate3(c, "G0", False, PC, gate), "G2": simulate3(c, "G2", True, PC, gate), "G3": simulate3(c, "G3", True, PC, gate)}; b = None
        for lab, r in res.items():
            r = dict(r); r["pay36"] *= n_acc; r["steady_m"] *= n_acc; r["net36"] = r["pay36"] - fee; r["annual_value"] = r["reach"] / 100 * r["steady_m"] * 12
            if lab == "G0": b = r
            v = "再現" if lab.startswith("Q88") else ("基準" if lab == "G0" else ("改善" if (r["net36"] >= b["net36"] and r["fail"] <= b["fail"] + 1.0 and (r["net36"] >= 1.1 * b["net36"] or r["fail"] <= b["fail"] - 3.0)) else ("悪化" if (r["net36"] < 0.9 * b["net36"] or r["fail"] > b["fail"] + 3.0) else "差なし")))
            rows.append(dict(cand=nm, form=lab, cells=1 if lab in ("G2", "G3") else 0, fee_man=round(fee, 1), verdict=v, **{k: (round(x, 1) if isinstance(x, float) else x) for k, x in r.items()}))
        print("done", nm[:40], flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q291_purchase_mc_guards.csv", index=False); assert int(D.cells.sum()) == NC
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 46)
    print(f"\n== Q291(累積セル {cum} + {NC} = {cum + NC}・到達 % / 失格 %(評価中 / 資金化後)/ 中央到達日 / 36 か月の出金・純益(万円)/ 定常の月次(万円)/ 年価値) =="); print(D[["cand", "form", "reach", "fail", "fail_eval", "fail_funded", "reach_med_days", "pay36", "net36", "steady_m", "annual_value", "pay36_p0", "verdict"]].to_string(index=False))
    print("\n候補ごとの採用形(悪化でない型の中で純益最大)と順位:"); pick = []
    for nm in D.cand.unique():
        x = D[(D.cand == nm) & D.form.isin(["G0", "G2", "G3"]) & (D.verdict != "悪化")].sort_values("net36", ascending=False).iloc[0]; g0 = D[(D.cand == nm) & (D.form == "G0")].iloc[0]; q = D[(D.cand == nm) & D.form.str.startswith("Q88")].iloc[0]; pick.append((x.net36, nm, x.form, x.reach, x.fail, g0.net36, q.net36))
    for i, (net, nm, form, reach, fail, g0n, qn) in enumerate(sorted(pick, reverse=True), 1): print(f"  {i}. {nm[:44]}: {form}・純益 {net:.1f} 万(G0 同期間 {g0n:.1f}・Q88 全期間 {qn:.1f})・到達 {reach:.1f}% / 失格 {fail:.1f}%")
    print(f"\nセルの判定: 改善 {int((D.verdict == '改善').sum())}・差なし {int((D.verdict == '差なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {NC}")
