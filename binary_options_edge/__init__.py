"""バイナリーオプション 統計的エッジ検証フレームワーク。

利益化の必要十分条件は『自分の勝率推定が継続的に P/100 を上回る（売りは下回る）こと』。
本パッケージはコスト控除後の期待値のみで判定し、エッジが無ければ無いと結論する。
"""
from . import backtest, data, hypotheses, pricing, risk, spread, stats_tests  # noqa

__all__ = ["pricing", "data", "spread", "hypotheses", "stats_tests", "risk", "backtest"]
