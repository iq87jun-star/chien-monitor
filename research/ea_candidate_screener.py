#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ea_candidate_screener.py — 外部EA/戦略候補の一次検証ハーネス (docs/184)
======================================================================

【目的】
  docs/183 で列挙した公開候補(Darwinex 4 / GogoJungle 7 / MQL5)を、
  公開ヘッドライン統計だけでどこまで検証できるかを実行する。

【方法】
  1. Darwinex は全 DARWIN が月次VaR(95%)=6.5% にリスク標準化されている。
     → implied 月次σ ≈ VaR95/1.645、年率σ ≈ 月次σ×√12 ≈ 13.7%。
     公開の年率リターンから implied 年率シャープを逆算できる。
  2. 有意性: ゼロスキル帰無仮説の p値 = 1 − Φ(SR_m × √T)。
  3. 多重検定割引 (docs/165 の規律の定量版, Bailey & López de Prado):
     N 本のゼロスキル戦略の最大シャープ期待値
       E[maxSR] ≈ (1/√T)·[(1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))]、γ=0.5772
     を「運のバー」とし、候補の SR がこれを超えるかを判定する。
     N は選抜母集団に依存: 本スクリーニングの短リスト N=11、
     DarwinIA GOLD 参加者 N=596(最悪ケース: 全期間SRで選んだと仮定した場合)。
     ※実際の選抜は「4月の月次リターン」であり全期間SRではないため、
       全期間SR への正しい割引は N=11 と N=596 の間(N=11 寄り)にある。
  4. GogoJungle 勢は月次系列が未取得のため定性ゲートのみ(次段でCSV要取得)。

【拡張】 monthly_returns に実系列(小数, 月次)を与えれば、実測SR・PSR で上書き評価する。
"""

import json
import math
import os

GAMMA = 0.5772156649
VAR95_M = 0.065            # Darwinex リスク標準化: 月次VaR95
SIGMA_M = VAR95_M / 1.645  # implied 月次σ ≈ 3.95%
SIGMA_A = SIGMA_M * math.sqrt(12.0)

TRIALS_GRID = [11, 140, 596]   # 短リスト / GOLD配分数 / GOLD参加者
OWN_ANCHOR_SHARPE = 1.71       # docs/46/47 自EAポートフォリオ(参考アンカー)

# ---- 候補 (2026-07-29 取得の公開値) --------------------------------------
DARWINEX = [
    # name, 年率リターン, 実績月数, 備考
    dict(name="PKR",  ann_ret=0.1008, months=77, note="実績2020-02〜(約7年)。DarwinIA GOLD 9位"),
    dict(name="ELW",  ann_ret=0.1562, months=48, note="実績2022-06〜(4年)。GOLD 10位"),
    dict(name="QCF",  ann_ret=0.1312, months=30, note="実績2.5年。Darwinex自己資本配分#5"),
    dict(name="OXTI", ann_ret=0.0979, months=27, note="実績2.5年。GOLD 1位(4月)。556取引・勝率41.4%・平均5h保有"),
]

GOGOJUNGLE = [
    dict(name="Iam Clown FX (Red)", fwd_years=7, pf=None, note="GGJ最長クラス・複利低速"),
    dict(name="ラスト侍EURUSD_5分足", fwd_years=6, pf=1.7,  note="低頻度・高選別"),
    dict(name="Unison",             fwd_years=5, pf=None, note="不利相場停止フィルタ"),
    dict(name="ESCADA-USDJPY",      fwd_years=5, pf=None, note="動的ロット(要精査)"),
    dict(name="一本勝ち",            fwd_years=None, pf=None, note="FW>BT・2100+ユーザー"),
    dict(name="BeeOne_USDJPY",      fwd_years=2, pf=1.42, note="BT2.11→FW1.42(ヘアカット実例)"),
    dict(name="CounterQ",           fwd_years=None, pf=None, note="逆張り・無料版あり"),
]


# ---- 数値ユーティリティ (stdlib のみ) --------------------------------------
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p):
    """Acklam の有理近似による標準正規の逆CDF。"""
    if not 0.0 < p < 1.0:
        raise ValueError("p in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def luck_bar_annual(n_trials, months):
    """N本のゼロスキル戦略の最大シャープ期待値(年率換算)= 運のバー。"""
    if n_trials <= 1:
        return 0.0
    e_max = (1 - GAMMA) * phi_inv(1 - 1.0 / n_trials) \
        + GAMMA * phi_inv(1 - 1.0 / (n_trials * math.e))
    return e_max / math.sqrt(months) * math.sqrt(12.0)


def eval_darwinex(c):
    sr_a = c["ann_ret"] / SIGMA_A                 # implied 年率シャープ
    sr_m = sr_a / math.sqrt(12.0)
    z = sr_m * math.sqrt(c["months"])
    pval = 1.0 - phi(z)                           # ゼロスキル帰無の p値
    bars = {n: luck_bar_annual(n, c["months"]) for n in TRIALS_GRID}
    verdict = "PASS" if sr_a > bars[11] else "FAIL"
    if verdict == "PASS" and sr_a < bars[11] * 1.25:
        verdict = "PASS(僅差)"
    return dict(name=c["name"], months=c["months"], ann_ret=c["ann_ret"],
                implied_sharpe=sr_a, p_value=pval, luck_bars=bars,
                verdict_vs_shortlist=verdict, note=c["note"])


def main():
    print("=" * 96)
    print("外部EA候補 一次検証 (docs/184) — implied Sharpe & 多重検定割引 / "
          f"Darwinex σ_a={SIGMA_A*100:.1f}% (VaR標準化)")
    print("=" * 96)

    print("\n[1] Darwinex 4候補 (定量ゲート)")
    print(f"  {'DARWIN':<6} {'実績':>5} {'年率':>7} {'impliedSR':>10} {'p値':>7} | "
          f"運のバー N=11 / N=140 / N=596 | 判定(vs N=11)")
    results = []
    for c in DARWINEX:
        r = eval_darwinex(c)
        results.append(r)
        b = r["luck_bars"]
        print(f"  {r['name']:<6} {r['months']:>4}月 {r['ann_ret']*100:>6.1f}% "
              f"{r['implied_sharpe']:>10.2f} {r['p_value']:>7.3f} | "
              f"{b[11]:>6.2f} / {b[140]:>6.2f} / {b[596]:>6.2f} | {r['verdict_vs_shortlist']}")
    print(f"\n  参考アンカー: 自EAポートフォリオ Sharpe {OWN_ANCHOR_SHARPE}(docs/46/47)")
    print("  ※選抜は「4月の月次リターン」であり全期間SRではないため、正しい運のバーは")
    print("    N=11 と N=596 の間(N=11寄り)。N=596 のバーは最悪ケースの参考値。")

    print("\n[2] GogoJungle 7候補 (定性ゲートのみ — 月次系列未取得)")
    print(f"  {'EA':<22} {'FW年数':>6} {'FW PF':>6}  判定")
    gg = []
    for c in GOGOJUNGLE:
        yrs = c["fwd_years"]
        ok = yrs is not None and yrs >= 5
        verdict = ("定量検証候補(要CSV)" if ok else
                   "保留(実績年数不足/不明)")
        gg.append(dict(**c, verdict=verdict))
        print(f"  {c['name']:<22} {str(yrs) if yrs else '-':>6} "
              f"{str(c['pf']) if c['pf'] else '-':>6}  {verdict}")

    print("\n[3] 結論")
    passed = [r for r in results if r["verdict_vs_shortlist"].startswith("PASS")]
    print(f"  ・定量ゲート通過: {', '.join(r['name'] for r in passed)} "
          f"(短リストN=11の運のバー超え)")
    print(f"  ・ただし全候補が自EAアンカー(SR {OWN_ANCHOR_SHARPE})未満 → 価値は分散(要相関確認)")
    print("  ・次段: Darwinex月次系列(要無料口座/API)・GGJフォワードCSV → 実測SR/相関で最終判定")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "ea_candidate_screen.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"sigma_a": SIGMA_A, "trials_grid": TRIALS_GRID,
                   "own_anchor_sharpe": OWN_ANCHOR_SHARPE,
                   "darwinex": results, "gogojungle": gg},
                  f, ensure_ascii=False, indent=2)
    print(f"\n結果JSON: {out}")


if __name__ == "__main__":
    main()
