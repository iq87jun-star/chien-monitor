"""6 ゲートを束ねて ADOPT / LEAD / REJECT を判定し、単一スカラ JSON を出力する。

6 ゲート（docs/26 規律 3）:
  G1 純益 > 0
  G2 順列 p（月次ブロック符号シャッフル）< α（=Bonferroni 0.05/N）
  G3 ジャックナイフ最大 p ≤ 0.10
  G4 曜日/プラセボで対象だけ突出
  G5 コスト（往復スプレッド・スワップ）計上後も生存（純益>0 を実コストで再評価）
  G6 v7 との 10年相関が低/負（|corr| ≤ 0.3 を低相関の目安。負ならなお良し）

判定:
  ADOPT  = G1..G6 全通過
  LEAD   = G2 未達だが G1・G3・G6 は通り、p が α..0.10 の "惜しい" 圏
  REJECT = それ以外
"""
import json

from . import stats


GATE_NAMES = ["G1_net_positive", "G2_perm_p", "G3_jackknife", "G4_placebo", "G5_cost", "G6_v7_corr"]


def evaluate(
    name: str, alpha: float, daily, index,
    placebo_dailies: dict, v7_corr: float,
    daily_cost_adjusted=None, block: str = "M",
    n_perm: int = 5000, corr_threshold: float = 0.30,
):
    """各ゲートを評価して結果 dict を返す。daily は R 単位の日次系列。"""
    net = float(sum(daily))
    p_val, obs = stats.block_sign_perm_pvalue(daily, index, block=block, n_perm=n_perm)
    p_jack, jack_detail = stats.jackknife_year_pvalues(daily, index, block=block, n_perm=max(1000, n_perm // 2))
    placebo = stats.placebo_standout(daily, placebo_dailies)
    cost_series = daily_cost_adjusted if daily_cost_adjusted is not None else daily
    net_cost = float(sum(cost_series))

    g1 = net > 0
    g2 = p_val < alpha
    g3 = p_jack <= 0.10
    g4 = bool(placebo["standout"])
    g5 = net_cost > 0
    g6 = (v7_corr != v7_corr) is False and abs(v7_corr) <= corr_threshold  # NaN は不可
    gates = {
        "G1_net_positive": g1,
        "G2_perm_p": g2,
        "G3_jackknife": g3,
        "G4_placebo": g4,
        "G5_cost": g5,
        "G6_v7_corr": g6,
    }
    all_pass = all(gates.values())
    if all_pass:
        verdict = "ADOPT"
    elif g1 and g3 and g6 and (alpha <= p_val <= 0.10):
        verdict = "LEAD"
    else:
        verdict = "REJECT"

    return {
        "name": name,
        "alpha": alpha,
        "verdict": verdict,
        "gates": gates,
        "scalars": {
            "net_R": round(net, 4),
            "net_R_cost": round(net_cost, 4),
            "sharpe": round(stats.sharpe(daily), 4),
            "perm_p": round(p_val, 5),
            "observed_stat": round(obs, 4),
            "jackknife_max_p": round(p_jack, 4),
            "v7_corr": (round(v7_corr, 4) if v7_corr == v7_corr else None),
            "placebo_target": placebo["target"],
            "placebo_best": (max(placebo["placebos"].values()) if placebo["placebos"] else None),
        },
        "jackknife_by_year": jack_detail,
        "placebo": placebo,
    }


def dump_json(result: dict, path: str | None = None) -> str:
    txt = json.dumps(result, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
    return txt


def print_summary(result: dict):
    s = result["scalars"]
    print(f"=== {result['name']}  [{result['verdict']}]  (alpha={result['alpha']}) ===")
    for k, v in result["gates"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"  net_R={s['net_R']}  cost_net_R={s['net_R_cost']}  sharpe={s['sharpe']}")
    print(f"  perm_p={s['perm_p']}  jackknife_max_p={s['jackknife_max_p']}  v7_corr={s['v7_corr']}")
