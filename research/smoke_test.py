"""
smoke_test.py — 合成データで4 runner を端から端まで実行し、クラッシュ/IF不整合を検出する。

※これは「動作（落ちない・JSONが出る）」の確認であって、エッジの有無の検定ではない。
   拘束力ある判定は Drive 上の実10年データで行う（docs/26 §0,§6）。
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import importlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

FX = ["AUDJPY", "CADJPY", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD",
      "USDJPY", "USDCHF", "USDCAD", "USDSEK", "USDNOK"]
IDX = ["US500", "NAS100", "JP225"]
CCYS = ["USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "SEK", "NOK"]


def synth_h1(path: str, base: float, vol: float, seed: int):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", "2020-12-31 23:00", freq="h", tz="UTC")
    steps = rng.normal(0, vol, len(idx))
    close = base * np.exp(np.cumsum(steps) / 100.0)
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, vol / 200, len(idx))))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, vol / 200, len(idx))))
    pd.DataFrame({"time": idx, "open": op, "high": hi, "low": lo,
                  "close": close, "volume": 1000}).to_csv(path, index=False)


def build_synthetic(d: str):
    for i, s in enumerate(FX):
        base = 130.0 if s.endswith("JPY") and s.startswith("USD") else \
               95.0 if s.endswith("JPY") else 1.2
        synth_h1(os.path.join(d, f"{s}_h1.csv"), base, vol=0.8, seed=i + 1)
    for i, s in enumerate(IDX):
        synth_h1(os.path.join(d, f"{s}_h1.csv"), base=3000.0, vol=1.2, seed=100 + i)

    # v7 週次リターン（無相関の合成）
    rng = np.random.default_rng(7)
    w = pd.date_range("2018-01-01", "2020-12-31", freq="W-MON", tz="UTC")
    pd.DataFrame({"date": w, "ret": rng.normal(0.001, 0.004, len(w))}).to_csv(
        os.path.join(d, "v7_weekly_returns.csv"), index=False)

    # コスト表（全シンボル）
    rows = [{"symbol": s, "roundtrip_cost_frac": 0.00006, "swap_frac_per_night": 0.00002}
            for s in FX + IDX]
    pd.DataFrame(rows).to_csv(os.path.join(d, "costs.csv"), index=False)

    # 政策金利（月次・全通貨）
    months = pd.date_range("2018-01-01", "2020-12-31", freq="MS", tz="UTC")
    rates = {"date": np.repeat(months, len(CCYS)),
             "ccy": CCYS * len(months),
             "rate": np.tile(np.linspace(0.0, 2.5, len(CCYS)), len(months))}
    pd.DataFrame(rates).to_csv(os.path.join(d, "policy_rates_monthly.csv"), index=False)


def main():
    tmp = tempfile.mkdtemp(prefix="edge_smoke_")
    reports = os.path.join(tmp, "reports")
    os.makedirs(reports, exist_ok=True)
    os.environ["EDGE_DATA_DIR"] = tmp
    os.environ["EDGE_REPORTS_DIR"] = reports
    build_synthetic(tmp)

    ok = True
    for mod_name, out in [("edge3a_eqmr_10y", "edge3a_result.json"),
                          ("edge3b_leadlag_10y", "edge3b_result.json"),
                          ("edge3c_carry_10y", "edge3c_result.json"),
                          ("edge3d_session_10y", "edge3d_result.json")]:
        try:
            # data_io はモジュール import 時に env を読むので、毎回リロード
            import data_io
            importlib.reload(data_io)
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            mod.main()
            with open(os.path.join(reports, out)) as f:
                j = json.load(f)
            assert "grade" in j and "gates" in j
            print(f"  OK {mod_name:22s} grade={j['grade']:6s} "
                  f"n={j['n_trades']:5d} p_net={j['perm_p_net']:.4f} "
                  f"corr_v7={j['corr_v7']:+.3f} ddEqNotional={j['max_dd_equal_notional']:.4f}")
        except Exception as e:
            ok = False
            import traceback
            print(f"  FAIL {mod_name}: {e}")
            traceback.print_exc()
    print("SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
