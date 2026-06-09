# -*- coding: utf-8 -*-
"""
p1_july_start_sjul.py — 既存P1(v7:v4:E5 40:40:20)を「7月開始」でプロップ審査した時の
   到達月数MCに、S-Jul(指数7月ロング)の月1上乗せを当てはめる試算(docs/64 §8)。

背景: docs/63 は base=v4:E-Mon 55:45 で「中央3/4ヶ月」を試算した。本書はユーザーの
   実運用条件 ―― 既存プロップ(FundedNext Stellar P1 +8%/−10%)・既存P1ポート ―― に置換し、
   さらに「来月=7月スタート」を反映(カレンダー対応MC: 月1=7月, 以後12ヶ月毎に7月へS-Jul益を上乗せ)。

モデル:
   - P1 月次 = znorm(v7,v4,E5) を 40:40:20 で合成(portfolio_optimize/parallel_vs_existing_compare 再構築)。
   - サイズ S は p95年DD が −10% になる S10 基準。中央4=×1.47 / 中央3=×1.96(本再構築)。
   - simulate: ブロックブートストラップ(block=3) + 7月位置に S-Jul 実7月益(US500+NAS100 L, 10年)×factor を加算。
   - factor → 月1上乗せpt = mean(S-Jul 7月益)×factor×S。サテライト(≈+1pt)/中(≈+2-3pt)/フル脚(≈+5-6pt)を比較。
規律: 数字は盛らない。月次解像度=失格は楽観。2016-2025の7月に大暴落無し=S-Jul下振れは楽観。
   Yahoo近似・v4は日足簡易再現。最終は Drive+デモで確定。「必ず通る手法」は存在しない。
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portfolio_optimize import aligned, znorm
from pstar_challenge_mc import find_scale, p95_annual_maxdd
from calendar_event_edge_10y import month_series

HERE = os.path.dirname(os.path.abspath(__file__))


def build_p1():
    Z = znorm(aligned(["v7", "v4", "E5"]))
    w = {"v7": .40, "v4": .40, "E5": .20}
    return sum(Z[k] * w[k] for k in w).dropna()


def sjul_july_returns():
    sj = (month_series("US500", 7, +1) + month_series("NAS100", 7, +1)) / 2
    return ((1 + sj).groupby(pd.to_datetime(sj.index).year).prod() - 1).values


def simulate_july_start(P1, scale, target, sjul_vals, factor=0.0,
                        max_loss=0.10, n_paths=40000, cap=72, block=3, seed=7, start_month=7):
    w = P1.values * scale; n = len(w); rng = np.random.default_rng(seed)
    P = np.empty((n_paths, cap))
    for p in range(n_paths):
        seq = []
        while len(seq) < cap:
            st = rng.integers(0, n); seq.extend(w[(st + k) % n] for k in range(block))
        P[p] = seq[:cap]
    if factor > 0:
        for m in range(cap):
            if ((start_month - 1) + m) % 12 == 6:           # この月が7月
                P[:, m] = P[:, m] + rng.choice(sjul_vals, size=n_paths) * factor
    months = []; passed = failed = 0
    for i in range(n_paths):
        eq = 1.0
        for m in range(cap):
            eq *= (1 + P[i, m])
            if eq <= 1 - max_loss:
                failed += 1; break
            if eq >= 1 + target:
                passed += 1; months.append(m + 1); break
    mo = np.array(months) if months else np.array([cap])
    return dict(med=int(np.median(mo)), mean=round(float(mo.mean()), 2),
                le3=round(float((mo <= 3).mean()) * 100, 1), le4=round(float((mo <= 4).mean()) * 100, 1),
                pass_pct=round(passed / n_paths * 100, 1), fail_pct=round(failed / n_paths * 100, 1))


def scale_for_median(P1, ref, target, want, lo=0.2, hi=6.0, n=12000):
    rng_seed = 11
    def med(s):
        from pstar_challenge_mc import block_paths
        Pp = block_paths(P1.values * s, n, 72, 3, rng_seed); m = []
        for i in range(n):
            eq = 1.0
            for k in range(72):
                eq *= 1 + Pp[i, k]
                if eq <= 0.9: m.append(72); break
                if eq >= 1 + target: m.append(k + 1); break
            else: m.append(72)
        return int(np.median(m))
    for _ in range(30):
        mid = (lo + hi) / 2
        if med(mid * ref) <= want: hi = mid
        else: lo = mid
    return hi * ref


def main():
    P1 = build_p1(); S10 = find_scale(P1, -10.0); sjv = sjul_july_returns()
    print(f"P1=v7:v4:E5 40:40:20  n={len(P1)}  S10(−10%枠)={S10:.3f}  "
          f"S-Jul実7月益: 平均{np.mean(sjv)*100:+.2f}% 最悪{np.min(sjv)*100:+.2f}% 最良{np.max(sjv)*100:+.2f}%")
    out = {"S10": round(S10, 3), "sjul_jul_mean_pct": round(float(np.mean(sjv) * 100), 2),
           "sjul_jul_worst_pct": round(float(np.min(sjv) * 100), 2), "scenarios": {}}
    for tgt, fname in [(0.08, "FundedNext +8%"), (0.10, "(参考)FTMO +10%")]:
        print("\n" + "=" * 78 + f"\n{fname} / 既存P1 / 7月開始")
        for want in (4, 3):
            S = scale_for_median(P1, S10, tgt, want)
            print(f"  --- 中央{want}ヶ月狙い ×{S/S10:.2f} (p95DD {p95_annual_maxdd(P1,S):.0f}%) ---")
            print(f"    {'サイズ':12s}{'月1上乗':>8}{'中央':>5}{'平均':>6}{'3内':>7}{'4内':>7}{'通過':>7}{'失格':>7}")
            f_sat = 0.01 / (np.mean(sjv) * S)
            for f, t in [(0, "S-Jul無"), (f_sat, "ｻﾃﾗｲﾄ+1pt"), (0.10, "中ｻｲｽﾞ"), (0.20, "ﾌﾙ脚相当")]:
                r = simulate_july_start(P1, S, tgt, sjv, factor=f)
                b = round(float(np.mean(sjv) * f * S * 100), 1)
                print(f"    {t:12s}{('+'+str(b)+'pt'):>8}{r['med']:>5}{r['mean']:>6}{r['le3']:>6}%{r['le4']:>6}%{r['pass_pct']:>6}%{r['fail_pct']:>6}%")
                out["scenarios"][f"{fname}|median{want}|{t}"] = dict(mult=round(S / S10, 2), month1_pt=b, **r)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "p1_july_start_sjul.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/p1_july_start_sjul.json")


if __name__ == "__main__":
    main()
