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


def test_martingale_guard_blocks_doubling():
    g = risk.MartingaleGuard(base_stake=50)
    g.check(50)
    g.record_result(won=False)   # 負け
    with pytest.raises(risk.MartingaleError):
        g.check(100)             # 倍賭けは禁止


def test_martingale_guard_allows_constant_after_loss():
    g = risk.MartingaleGuard(base_stake=50)
    g.check(50)
    g.record_result(won=False)
    g.check(50)                  # 同額は許可
    g.record_result(won=True)
    g.check(50)


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
