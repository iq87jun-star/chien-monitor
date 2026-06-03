"""
v7_size_finalize.py — v7 の推奨サイズ確定（p95ブートストラップDD基準, docs/29の較正規約）。

各レバ（=週次リスク%・原典規約）での p95最悪DD を出し、各口座の−10%枠に収まる推奨を決める。
- 現行プロップ（FundedNext Stellar 2-step, 静的−10%）: p95DD ≤ ~7% を目安。
- インスタント（−10%トレーリング）: より保守側 ≤ ~6%。
"""
from __future__ import annotations

import json
import numpy as np

from data_io import report_path
from v7_sim import original_convention_weekly, bootstrap_p95_maxdd


def main():
    levs = [0.4, 0.5, 0.6, 0.7, 0.75, 1.0, 1.5, 2.5]
    grid = {}
    print(f"{'lev(週次%)':>10} {'p95DD%':>8} {'10yNet%':>9}")
    for lev in levs:
        w = original_convention_weekly(lev)
        p95 = bootstrap_p95_maxdd(w)
        net = float(((1 + w).prod() - 1) * 100)
        grid[lev] = {"p95_maxDD": round(p95, 2), "net_10y": round(net, 1)}
        print(f"{lev:10.2f} {p95:8.2f} {net:9.1f}")

    # 推奨選定
    def pick(cap):
        ok = [l for l in levs if grid[l]["p95_maxDD"] <= cap]
        return max(ok) if ok else min(levs)
    rec_static = pick(7.0)
    rec_trail = pick(6.0)
    out = {"basis": "p95 block-bootstrap maxDD, original leverage convention (docs/29)",
           "grid": {str(k): v for k, v in grid.items()},
           "recommend_static_minus10": rec_static,
           "recommend_trailing_minus10": rec_trail}
    with open(report_path("v7_size.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n推奨: 静的−10%口座 → lev {rec_static}（p95DD {grid[rec_static]['p95_maxDD']}%）")
    print(f"推奨: トレーリング−10%口座 → lev {rec_trail}（p95DD {grid[rec_trail]['p95_maxDD']}%）")
    print(f"[WROTE] {report_path('v7_size.json')}")


if __name__ == "__main__":
    main()
