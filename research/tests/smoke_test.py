#!/usr/bin/env python3
"""ハーネスのスモークテスト。合成データで lib/* が破綻なく動くことだけ確認する
（拘束力ある検定ではない。実データは Drive で）。

合成データを一時ディレクトリに書き、CHIEN_DATA_DIR でそこを向かせて
edge3/edge6 と v7 参照・各ゲートを実行する。
"""
import os
import sys
import tempfile
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lib import data, engine, stats, evaluate, v7_reference  # noqa: E402


def _make_data(d):
    rng = np.random.default_rng(42)
    # 10年ぶんの H1 / 日足を合成
    h1_idx = pd.date_range("2016-01-01", "2025-12-31", freq="1h", tz="UTC")
    for sym, base in (("EURJPY", 130), ("GBPJPY", 150), ("USDJPY", 110)):
        # 月曜午前にわずかな正ドリフトを混ぜる（v7 が拾えるか）
        steps = rng.normal(0, 0.05, len(h1_idx))
        mon_am = (h1_idx.dayofweek == 0) & (h1_idx.hour.isin((4, 6, 8, 10)))
        steps[mon_am] += 0.04
        close = base + np.cumsum(steps)
        df = pd.DataFrame({"time": h1_idx, "open": close, "high": close + 0.1,
                           "low": close - 0.1, "close": close})
        df.to_csv(os.path.join(d, f"{sym}_h1.csv"), index=False)

    d_idx = pd.date_range("2016-01-01", "2025-12-31", freq="1D", tz="UTC")
    for sym, base, vol in (("XAUUSD", 1500, 15), ("SPX", 3000, 30),
                           ("VIX", 18, 4), ("US2Y", 1.5, 0.05), ("USDJPY", 110, 0.6)):
        close = base + np.cumsum(rng.normal(0, vol * 0.05, len(d_idx)))
        if sym == "VIX":
            close = np.abs(close) + 10
        df = pd.DataFrame({"time": d_idx, "open": close, "high": close * 1.01,
                           "low": close * 0.99, "close": close})
        df.to_csv(os.path.join(d, f"{sym}_d.csv"), index=False)

    ev_idx = d_idx[(d_idx.day == 15) & (d_idx.month.isin((3, 6, 9, 12)))]
    pd.DataFrame({"time": ev_idx, "kind": "FOMC"}).to_csv(
        os.path.join(d, "events_cb_d.csv"), index=False)


def main():
    with tempfile.TemporaryDirectory() as d:
        _make_data(d)
        os.environ["CHIEN_DATA_DIR"] = d

        # data ローダ
        assert data.available("EURJPY", "h1")
        assert len(data.load_h1("USDJPY")) > 1000
        assert len(data.load_daily("VIX")) > 1000

        # v7 参照
        v7w = v7_reference.v7_weekly_R()
        assert len(v7w) > 100, "v7 weekly empty"
        print(f"[ok] v7 weekly R: n={len(v7w)} mean={v7w.mean():.4f}")

        # stats ゲート（合成: 平均ゼロに近い → p は高めのはず）
        rng = np.random.default_rng(1)
        idx = pd.date_range("2016-01-01", periods=500, freq="1D", tz="UTC")
        noise = rng.normal(0, 1, 500)
        p, obs = stats.block_sign_perm_pvalue(noise, idx, n_perm=500)
        assert 0 < p <= 1
        signal = rng.normal(0.5, 1, 500)
        p2, _ = stats.block_sign_perm_pvalue(signal, idx, n_perm=500)
        print(f"[ok] perm p: noise={p:.3f} (high) signal={p2:.3f} (low)")
        assert p2 < p, "perm test should separate signal from noise"

        pj, _ = stats.jackknife_year_pvalues(signal, idx, n_perm=300)
        print(f"[ok] jackknife max p = {pj:.3f}")

        # engine: FX トレード + MC
        h1 = data.load_h1("EURJPY")
        entries = h1.index[(h1.index.dayofweek == 0) & (h1.index.hour == 4)]
        tr = engine.event_trades_fx(h1, entries, +1, 24)
        assert len(tr) > 100
        dR = engine.daily_R(tr)
        mc = engine.mc_pass_rate(dR, per_shot_risk_pct=0.6)
        print(f"[ok] FX trades={len(tr)} daily={len(dR)} MC pass={mc['pass_rate']}")

        # evaluate: フル 6 ゲート（edge6 を実行）
        import importlib.util
        for mod in ("edge3_vol_regime_10y", "edge6_index_meanrev_10y"):
            spec = importlib.util.spec_from_file_location(mod, os.path.join(ROOT, f"{mod}.py"))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            m.main()
        # 出力 JSON が単一スカラを持つか
        import json
        with open(os.path.join(ROOT, "..", "reports", "edge6_result.json")) as f:
            r = json.load(f)
        assert "verdict" in r and "gates" in r and len(r["gates"]) == 6
        print(f"[ok] edge6 verdict={r['verdict']} gates={sum(r['gates'].values())}/6")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
