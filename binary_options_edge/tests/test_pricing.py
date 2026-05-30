"""価格式の正しさ: 解析解 vs モンテカルロ、EV/損益分岐の符号。"""
import math

import pytest

from binary_options_edge import pricing


def test_atm_ladder_is_half():
    # ATM・ドリフト0 ではほぼ50%（-0.5σ²Tのわずかな下げのみ）
    p = pricing.prob_finish_above(150.0, 150.0, sigma=0.08, ttm_seconds=1800)
    assert 0.48 < p < 0.50


def test_ladder_matches_mc():
    s, k, sig, T = 150.0, 150.3, 0.10, 3600.0
    ana = pricing.prob_finish_above(s, k, sig, T)
    mc = pricing.mc_prob(s, sig, T, "finish_above", level=k, n_paths=200_000, seed=1)
    assert abs(ana - mc) < 0.01


def test_touch_matches_mc():
    s, h, sig, T = 150.0, 150.4, 0.10, 3600.0
    ana = pricing.prob_touch(s, h, sig, T)
    mc = pricing.mc_prob(s, sig, T, "touch", level=h, n_paths=200_000, n_steps=512, seed=2)
    # 連続監視の離散化バイアスを許容
    assert abs(ana - mc) < 0.02


def test_touch_prob_ge_finish_prob():
    # 同じ上バリアでは「触れる」確率 >= 「上で終わる」確率
    s, h, sig, T = 150.0, 150.5, 0.12, 3600.0
    assert pricing.prob_touch(s, h, sig, T) >= pricing.prob_finish_above(s, h, sig, T) - 1e-9


def test_range_matches_mc():
    s, lo, up, sig, T = 150.0, 149.7, 150.3, 0.10, 3600.0
    ana = pricing.prob_finish_in_range(s, lo, up, sig, T)
    mc = pricing.mc_prob(s, sig, T, "finish_in_range", lower=lo, upper=up,
                         n_paths=200_000, seed=3)
    assert abs(ana - mc) < 0.01


def test_ev_and_breakeven():
    # フェア=50, ask=53 なら買いはEV<0、p=0.55ならEV>0
    assert pricing.ev_buy(0.50, 53) == pytest.approx(-3.0)
    assert pricing.ev_buy(0.55, 53) == pytest.approx(2.0)
    assert pricing.breakeven_prob_buy(53) == 0.53
    assert pricing.required_prob_edge(6.0) == 0.03


def test_decide_trade_no_trade_zone():
    # bid48/ask52 のとき p=0.50 はノートレード帯
    d = pricing.decide_trade(0.50, bid=48, ask=52)
    assert d.side == "none"
    # p=0.60 なら買い
    d2 = pricing.decide_trade(0.60, bid=48, ask=52)
    assert d2.side == "buy" and d2.ev_points == pytest.approx(8.0)
    # p=0.40 なら売り
    d3 = pricing.decide_trade(0.40, bid=48, ask=52)
    assert d3.side == "sell" and d3.ev_points == pytest.approx(8.0)


def test_realized_pnl():
    assert pricing.realized_pnl_points("buy", True, 48, 52) == pytest.approx(48.0)
    assert pricing.realized_pnl_points("buy", False, 48, 52) == pytest.approx(-52.0)
    assert pricing.realized_pnl_points("sell", False, 48, 52) == pytest.approx(48.0)
    assert pricing.realized_pnl_points("sell", True, 48, 52) == pytest.approx(-52.0)
