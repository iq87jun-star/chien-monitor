"""リスク管理: サイジング、DD/連敗停止、マーチンゲール禁止。"""
import pytest

from binary_options_edge import risk


def test_position_size_caps_loss():
    # equity 10000, 0.5% = 50 予算, 1枚最大損失 ask=52 -> 0枚
    assert risk.position_size(10_000, 52, 0.005) == 0
    # 1% = 100 予算 -> 1枚
    assert risk.position_size(10_000, 52, 0.01) == 1
    # 大きい資金
    assert risk.position_size(1_000_000, 50, 0.005) == 100


def test_fractional_kelly_negative_edge_zero():
    assert risk.fractional_kelly_buy(0.50, 53) == 0.0
    f = risk.fractional_kelly_buy(0.60, 50, fraction=0.25)
    assert 0 < f < 1


def test_martingale_guard_blocks_exceeding_fixed_fraction():
    # 固定比率0.5% = 資金10000で上限50。これを超える賭金（=倍賭け）は禁止。
    g = risk.MartingaleGuard(max_risk_fraction=0.005)
    g.check(50, equity=10_000)        # 上限ちょうどはOK
    with pytest.raises(risk.MartingaleError):
        g.check(100, equity=10_000)   # 上限超過 → 倍賭けとして拒否


def test_martingale_guard_allows_fixed_fractional_after_loss():
    # 負けて資金が減れば固定比率では賭金も減る（アンチマーチンゲール）。誤検知しない。
    g = risk.MartingaleGuard(max_risk_fraction=0.005)
    g.check(50, equity=10_000)
    g.check(45, equity=9_000)         # 0.005*9000=45。資金減で賭金も減 → 許可
    g.check(45, equity=9_000)


def test_drawdown_guard_halts():
    g = risk.DrawdownGuard(start_equity=10_000, max_drawdown_frac=0.15)
    assert not g.update(9_000, last_trade_won=False)   # DD10%
    assert g.update(8_400, last_trade_won=False)        # DD16% -> 停止
    assert g.halted


def test_consecutive_loss_halt():
    g = risk.DrawdownGuard(10_000, max_consecutive_losses=3)
    for _ in range(2):
        assert not g.update(9_999, last_trade_won=False)
    assert g.update(9_999, last_trade_won=False)        # 3連敗で停止
