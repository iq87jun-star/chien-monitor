"""自動エントリーsignalの安全ゲート検証。

最重要: エッジ未実証なら必ず hold（エントリーしない）こと。
証明書があっても、コスト控除後EV<=0や局面不一致なら hold になること。
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from binary_options_edge.data import BinaryContract, UnderlyingSource
from binary_options_edge.hypotheses import h_all
from binary_options_edge.signals import EdgeCertificate, SignalEngine, certify_edges


class _ConstVol(UnderlyingSource):
    """常に一定ボラ・一定spotを返すテスト用ソース。"""
    def __init__(self, sigma=0.08, spot=150.0):
        self._sigma, self._spot = sigma, spot

    def history(self, pair, start, as_of):
        ts = pd.date_range(start, as_of, periods=10, tz="UTC")
        return pd.DataFrame({"ts": ts, "bid": self._spot, "ask": self._spot,
                             "mid": self._spot})

    def realized_vol(self, pair, as_of, lookback_seconds, annualize=True):
        return self._sigma


def _contract(bid, ask, strike=150.3):
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    return BinaryContract(
        pair="USDJPY", option_type="ladder_above", decision_time=t0,
        expiry_time=t0 + pd.Timedelta(seconds=1800), spot_at_decision=150.0,
        bid=bid, ask=ask, strike=strike, settled_yes=None)


def test_no_certificate_always_holds():
    """証明書ゼロなら、どんな好条件でも必ず hold。"""
    eng = SignalEngine(underlying=_ConstVol(), certificates={}, hypotheses={"H0_all": h_all()})
    # ありえないほど安い ask（買えば必ずEV>0に見える）でも hold でなければならない
    sig = eng.generate(_contract(bid=1, ask=2))
    assert sig.side == "hold"
    assert "エッジ未実証" in sig.reason


def _cert(name="H0_all", dsr=0.99, n=500):
    return EdgeCertificate(hypothesis_name=name, mean_pnl_after_cost=1.0,
                           boot_ci_low=0.2, deflated_sharpe=dsr, n_trades=n,
                           significant_after_fdr=True)


def test_certificate_but_negative_ev_holds():
    """証明書があっても、コスト控除後EV<=0（ノートレード帯）なら hold。"""
    eng = SignalEngine(underlying=_ConstVol(), certificates={"H0_all": _cert()},
                       hypotheses={"H0_all": h_all()})
    # ATM付近 p~0.48、bid/ask を p を挟む狭帯にしてノートレード帯にする
    sig = eng.generate(_contract(bid=45, ask=52, strike=150.0))
    assert sig.side == "hold"
    assert "EV" in sig.reason or "ノートレード" in sig.reason


def test_certificate_and_positive_ev_emits_signal():
    """証明書あり & コスト控除後EV>0 & 局面一致なら buy/sell を出す。"""
    eng = SignalEngine(underlying=_ConstVol(), certificates={"H0_all": _cert()},
                       hypotheses={"H0_all": h_all()}, risk_fraction=0.05,
                       equity=100_000)
    # p_above(150->150.3) はおよそ0.46。ask を十分低くして買いEV>0を作る
    p = 0.46
    # 買いEV = 100p - ask > 0 となるよう ask=40, bid=38
    sig = eng.generate(_contract(bid=38, ask=40, strike=150.3))
    assert sig.side in ("buy", "sell")
    assert sig.actionable
    assert sig.units >= 1
    assert sig.ev_points > 0


def test_certify_edges_gate():
    """ゲート条件: 件数不足/CI下限<=0/DSR低/非有意 はいずれも証明書を出さない。"""
    summaries = [
        {"label": "good", "n_trades": 300, "boot_ci95": (0.5, 2.0),
         "deflated_sharpe(>0.95=signif)": 0.99, "mean_pnl_points_after_cost": 1.2},
        {"label": "few_trades", "n_trades": 10, "boot_ci95": (0.5, 2.0),
         "deflated_sharpe(>0.95=signif)": 0.99, "mean_pnl_points_after_cost": 1.2},
        {"label": "ci_crosses_zero", "n_trades": 300, "boot_ci95": (-0.1, 2.0),
         "deflated_sharpe(>0.95=signif)": 0.99, "mean_pnl_points_after_cost": 1.2},
        {"label": "low_dsr", "n_trades": 300, "boot_ci95": (0.5, 2.0),
         "deflated_sharpe(>0.95=signif)": 0.40, "mean_pnl_points_after_cost": 1.2},
    ]
    fdr = {"good": True, "few_trades": True, "ci_crosses_zero": True, "low_dsr": True}
    certs = certify_edges(summaries, fdr, min_trades=200, min_dsr=0.95)
    assert set(certs.keys()) == {"good"}


def test_certify_edges_requires_fdr_significance():
    """BH-FDRで非有意なら、他の条件を満たしても証明書は出ない。"""
    summaries = [{"label": "good", "n_trades": 300, "boot_ci95": (0.5, 2.0),
                  "deflated_sharpe(>0.95=signif)": 0.99,
                  "mean_pnl_points_after_cost": 1.2}]
    certs = certify_edges(summaries, {"good": False}, min_trades=200, min_dsr=0.95)
    assert certs == {}
