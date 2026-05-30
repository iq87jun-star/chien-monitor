"""End-to-end 実行例（合成データ）。

  python -m binary_options_edge.example_run

合成データは DGP にエッジを入れていないため、コスト控除後の平均EVは負（半スプレッド負け）
になるのが正しい。これが本フレームワークの健全性チェック（=エッジが無いものを無いと言えるか）。
実データで使うときは GBMUnderlying / make_contracts を data.py の実装に差し替える。
"""
from __future__ import annotations

import pandas as pd

from . import backtest
from .hypotheses import default_hypotheses
from .stats_tests import benjamini_hochberg
from .synthetic import EmptyCalendar, GBMUnderlying, make_contracts


def main() -> None:
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 30)

    u = GBMUnderlying(days=12)
    cal = EmptyCalendar()
    contracts = make_contracts(u, n=1000, assumed_spread=4.0)
    print(f"# 合成提示数: {len(contracts)} (assumed spread = 4.0 pt, エッジ無しDGP)")
    print("# 市場=真のボラでフェア付け / モデル=短窓(60s)実現ボラ推定(ノイズ有り) -> ズレでトレード発生")
    print("# エッジ無しDGPなので、約定トレードのコスト控除後EVは負(≈-半スプレッド)に収束するのが正解。\n")

    hyps = default_hypotheses()
    n_tried = len(hyps)
    # 短い vol_lookback で推定ノイズを大きくし、(エッジ無しの)トレードを発生させる。
    # ノイズは清算結果と無相関なので、トレードは出るが期待値は負(=エッジ無し)に留まる。
    vol_lb = 60.0

    summaries = []
    pvalues = {}
    for name, filt in hyps.items():
        res = backtest.run_backtest(contracts, u, cal, filt,
                                    vol_lookback_seconds=vol_lb, n_hypotheses_tried=n_tried)
        s = backtest.summarize(res, label=name)
        summaries.append(s)
        pvalues[name] = s.get("t_pvalue_mean>0", 1.0)

    summary_df = pd.DataFrame(summaries)
    print("## コスト控除後サマリ（仮説別）")
    print(summary_df[["label", "n_trades", "mean_pnl_points_after_cost",
                      "win_rate", "avg_breakeven_prob", "win_rate_minus_breakeven",
                      "deflated_sharpe(>0.95=signif)", "edge_detected_after_cost"]]
          .to_string(index=False))

    print("\n## 多重検定補正（Benjamini-Hochberg, FDR=0.10）")
    rejected = benjamini_hochberg(pvalues, fdr=0.10)
    for name, rej in rejected.items():
        print(f"  {name:16s} p={pvalues[name]:.3f}  significant_after_FDR={rej}")

    # ベースライン仮説でレジーム安定性とエクイティ曲線
    base = backtest.run_backtest(contracts, u, cal, hyps["H0_all"],
                                 vol_lookback_seconds=vol_lb, n_hypotheses_tried=n_tried)
    print("\n## レジーム別安定性（H0_all, コスト控除後）")
    print(backtest.regime_stability(base).to_string(index=False))

    # デモ用に固定比率2%（実運用推奨は0.5%）。負EVのDGPなので半スプレッド分だけ逓減するはず
    eq = backtest.equity_curve(base, start_equity=10_000, risk_fraction=0.02)
    if not eq.empty:
        final = eq["equity"].iloc[-1]
        print(f"\n## エクイティ曲線（固定比率2%(デモ), DD15%停止）: "
              f"開始10,000 -> 終了 {final:,.0f}")
        if eq["halted"].iloc[-1]:
            print(f"   停止理由: {eq['reason'].iloc[-1]}")

    # 自動エントリーsignal: 検証ゲートを通った仮説の証明書を作り、提示に対し signal を出す
    from .signals import SignalEngine, certify_edges
    certs = certify_edges(summaries, rejected, min_trades=200, min_dsr=0.95)
    engine = SignalEngine(underlying=u, certificates=certs, hypotheses=hyps,
                          calendar=cal, vol_lookback_seconds=vol_lb)
    signals = engine.generate_batch(contracts)
    n_actionable = sum(s.actionable for s in signals)
    print("\n## 自動エントリーsignal")
    print(f"  発行された証明書(検証済みエッジ): {len(certs)} 件 -> {list(certs.keys())}")
    print(f"  エントリーsignal(buy/sell): {n_actionable} 件 / hold: {len(signals) - n_actionable} 件")
    if n_actionable == 0:
        print("  => 検証済みエッジが無いため、自動シグナルは全て『エントリーなし(hold)』。")
        print("     これは合成(エッジ無し)データに対する客観的に正しい挙動。")
        # holdの代表理由を1つ表示
        if signals:
            print(f"     例: {signals[0].reason}")

    print("\n## 結論の読み方")
    print("  - edge_detected_after_cost が False かつ DSR<=0.95 なら『コスト控除後エッジ無し』。")
    print("  - 合成（エッジ無し）データでは平均EVが負になるのが正しい挙動。")
    print("  - 実データで偶然 True が出ても、BH/DSR/レジーム一貫性/OOS乖離で必ず裏取りすること。")
    print("  - 自動エントリーは『検証済みエッジの証明書』が無い限り hold。捏造は構造的に不可能。")


if __name__ == "__main__":
    main()
