# -*- coding: utf-8 -*-
"""
compliant_lowfail_x2.py — FTMO準拠版・超攻め×2.0の「速さを保って失格率だけ下げる」手段を実測。

ベース: 準拠版(v4full:E-Mon 55:45)・×2.0(攻め−10%枠の2倍レバ)。P1+10%/−10%(FTMO)。
失格率を下げる候補(サイズ平均は落とさない=速さ維持):
  (G) ガード: 月内損失を −floor% で打ち切る(EAの−9%フロア/日次ストップが月の悪化を止める近似)。
  (D) 目標接近デリスク: 含み益が +thr% を超えたらサイズを factor 倍に絞る(バッファを守る)。
  (V) ボラ・ターゲティング: 直近実現ボラに反比例でサイズ調整(荒れたら自動縮小・凪で復帰)。
  (GDV) 三者併用。
手法: ブロックBS月次2万パス。各手段でP1通過%/失格%/中央月を比較。
規律: 数字は盛らない。月次解像度=失格は楽観だが"手段の相対効果"は読める。実装はEA側で要再現+デモ。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v4_monthly, emon_monthly, z
from pstar_challenge_mc import find_scale, block_paths

HERE = os.path.dirname(os.path.abspath(__file__))


def compliant_monthly():
    M = pd.DataFrame({"v4full": v4_monthly(), "E-Mon": emon_monthly()}).dropna()
    return (0.55 * z(M["v4full"]) + 0.45 * z(M["E-Mon"])).dropna()


def simulate(series, scale, target=0.10, max_loss=0.10, cap_m=72, n_paths=20000, block=3, seed=7,
             floor=None, derisk_thr=None, derisk_factor=1.0, vol_target=None, vol_win=3):
    """各手段をオプションで適用してP1判定。floor=月内損失上限, derisk=益超でサイズ縮小, vol_target=ボラ調整。"""
    P = block_paths(series.values * scale, n_paths, cap_m, block=block, seed=seed)
    base_sigma = series.std() * scale
    months = []; passed = failed = timeout = 0
    for i in range(n_paths):
        eq = 1.0; done = False; recent = []
        for m in range(cap_m):
            r = P[i, m]
            size = 1.0
            # (V) ボラ・ターゲティング
            if vol_target is not None and len(recent) >= vol_win:
                rv = np.std(recent[-vol_win:]) or base_sigma
                size *= min(1.0, vol_target / rv) if rv > 0 else 1.0
            # (D) 目標接近デリスク
            if derisk_thr is not None and (eq - 1.0) >= derisk_thr:
                size *= derisk_factor
            r_eff = r * size
            # (G) 月内損失上限(ガードが悪化を打ち切る近似)
            if floor is not None:
                r_eff = max(r_eff, -floor)
            recent.append(r)              # ボラ推定は素リターンで
            eq *= (1 + r_eff)
            if eq <= 1.0 - max_loss:
                failed += 1; done = True; break
            if eq >= 1.0 + target:
                passed += 1; months.append(m + 1); done = True; break
        if not done:
            timeout += 1
    months = np.array(months) if months else np.array([cap_m])
    return dict(pass_pct=round(passed / n_paths * 100, 1), fail_pct=round(failed / n_paths * 100, 1),
                med=int(np.median(months)), p75=int(np.percentile(months, 75)))


def main():
    s = compliant_monthly()
    S10 = find_scale(s, -10.0); S = S10 * 2.0     # 超攻め×2.0
    bv = s.std() * S                              # ×2.0時の月次ボラ(=vol_targetの基準)

    print("=" * 92)
    print("FTMO準拠版・超攻め×2.0：失格率を下げる手段の効果（P1 +10%/−10%・2万パス）")
    print("=" * 92)
    print(f"{'手段':40s}{'P1通過%':>8}{'P1失格%':>8}{'中央月':>8}{'75%月':>7}")
    variants = [
        ("(ベース)×2.0 手当なし", dict()),
        ("(G)月内損失上限 floor=4%", dict(floor=0.04)),
        ("(D)+6%超で半減 derisk", dict(derisk_thr=0.06, derisk_factor=0.5)),
        ("(V)ボラ・ターゲティング", dict(vol_target=bv * 0.9)),
        ("(G+D)ガード+デリスク", dict(floor=0.04, derisk_thr=0.06, derisk_factor=0.5)),
        ("★(G+D+V)三者併用", dict(floor=0.04, derisk_thr=0.06, derisk_factor=0.5, vol_target=bv * 0.9)),
    ]
    out = {}
    for nm, kw in variants:
        r = simulate(s, S, **kw); out[nm] = r
        print(f"{nm:40s}{r['pass_pct']:>8}{r['fail_pct']:>8}{r['med']:>8}{r['p75']:>7}")

    print("\n[読み方] 目標=『中央月(速さ)を保ったまま失格%を下げる』。floorは月内損失をガードで打ち切る近似、")
    print("  derisk=+6%バッファを守る、vol-target=荒れた局面で自動縮小。実効サイズの平均は大きく落とさない。")
    print("  ⚠ 月次解像度ゆえ失格の絶対値は楽観。だが各手段の相対効果(どれが効くか)は信頼できる。")
    with open(os.path.join(HERE, "results", "compliant_lowfail_x2.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/compliant_lowfail_x2.json")


if __name__ == "__main__":
    main()
