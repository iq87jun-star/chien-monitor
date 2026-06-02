#!/usr/bin/env python3
"""4 候補（E3-E6）を順に実行し、判定を1枚に集約する。

使い方（Drive にデータを置いた Colab / ローカル）:
    export CHIEN_DATA_DIR=/content/drive/MyDrive/chien-monitor/data
    python3 research/run_all.py

各候補の reports/edgeN_result.json を生成し、reports/edge3_4_summary.json と
コンソールに ADOPT/LEAD/REJECT の表を出す。データ欠損の候補は SKIP（理由つき）。
"""
import os
import sys
import json
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from lib import evaluate  # noqa: E402

CANDIDATES = [
    ("E3", "edge3_vol_regime_10y", "edge3_result.json"),
    ("E4", "edge4_rates_jpy_leadlag_10y", "edge4_result.json"),
    ("E5", "edge5_event_drift_10y", "edge5_result.json"),
    ("E6", "edge6_index_meanrev_10y", "edge6_result.json"),
]


def _run(mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(ROOT, f"{mod_name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.main()


def main():
    summary = []
    for cid, mod, out in CANDIDATES:
        print(f"\n########## {cid} ({mod}) ##########")
        try:
            _run(mod)
            with open(evaluate.reports_path(out), encoding="utf-8") as f:
                r = json.load(f)
            summary.append({
                "id": cid, "name": r["name"], "verdict": r["verdict"],
                "gates_passed": sum(r["gates"].values()),
                "perm_p": r["scalars"]["perm_p"],
                "jackknife_max_p": r["scalars"]["jackknife_max_p"],
                "v7_corr": r["scalars"]["v7_corr"],
                "net_R_cost": r["scalars"]["net_R_cost"],
            })
        except FileNotFoundError as e:
            print(f"[SKIP {cid}] データ欠損: {e}")
            summary.append({"id": cid, "verdict": "SKIP", "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR {cid}] {type(e).__name__}: {e}")
            summary.append({"id": cid, "verdict": "ERROR", "reason": str(e)})

    print("\n================ SUMMARY ================")
    print(f"{'ID':<4}{'VERDICT':<9}{'gates':<7}{'perm_p':<9}{'jk_max_p':<10}{'v7_corr':<9}{'net_R_cost'}")
    for s in summary:
        if s["verdict"] in ("SKIP", "ERROR"):
            print(f"{s['id']:<4}{s['verdict']:<9}{s.get('reason','')[:60]}")
        else:
            print(f"{s['id']:<4}{s['verdict']:<9}{s['gates_passed']}/6    "
                  f"{s['perm_p']:<9}{s['jackknife_max_p']:<10}{str(s['v7_corr']):<9}{s['net_R_cost']}")
    adopt = [s["id"] for s in summary if s["verdict"] == "ADOPT"]
    lead = [s["id"] for s in summary if s["verdict"] == "LEAD"]
    print("\n結論:",
          f"ADOPT={adopt or 'なし'} / LEAD={lead or 'なし'}",
          "→ ADOPT が無ければ『3本目なし』と正直に結論する（それも価値ある結果）。")
    spath = evaluate.reports_path("edge3_4_summary.json")
    with open(spath, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("->", spath)


if __name__ == "__main__":
    main()
