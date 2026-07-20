"""empirical.py の純関数（ネットワーク不要部分）のテスト。"""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from binary_options_edge import empirical


def test_us_dst_boundaries():
    assert empirical._us_dst(date(2026, 7, 20))       # 夏
    assert not empirical._us_dst(date(2026, 1, 15))   # 冬
    assert empirical._us_dst(date(2026, 3, 8))        # 2026年DST開始日(第2日曜)
    assert not empirical._us_dst(date(2026, 11, 1))   # 終了日


def test_first_friday():
    assert empirical._first_friday(2026, 7) == date(2026, 7, 3)
    assert empirical._first_friday(2026, 8) == date(2026, 8, 7)


def test_calendar_known_events():
    cal = empirical.build_event_calendar(date(2026, 6, 1), date(2026, 7, 20))
    known = {(r["event"], r["date"]) for _, r in cal.iterrows()}
    assert ("CPI", date(2026, 7, 14)) in known
    assert ("NFP", date(2026, 7, 2)) in known       # 独立記念日振替の例外
    assert ("FOMC", date(2026, 6, 17)) in known
    # 夏時間: 8:30 ET = 12:30 UTC
    cpi = cal[(cal["event"] == "CPI") & (cal["date"] == date(2026, 7, 14))].iloc[0]
    assert cpi["utc"].hour == 12 and cpi["utc"].minute == 30


def test_calendar_excludes_shutdown_period():
    cal = empirical.build_event_calendar(date(2025, 10, 1), date(2025, 12, 31))
    assert not ((cal["event"] == "NFP")).any()      # 閉鎖期のNFPは除外
    assert not ((cal["event"] == "CPI")).any()


def test_log_returns_skips_weekend_gaps():
    idx = pd.to_datetime(["2026-07-17 20:00", "2026-07-17 21:00",
                          "2026-07-19 21:00"], utc=True)   # 週末ギャップを含む
    df = pd.DataFrame({"close": [100.0, 101.0, 105.0]}, index=idx)
    lr = empirical.log_returns(df, interval_seconds=3600.0)
    assert len(lr) == 1                              # ギャップ越えは除外
    assert lr.iloc[0] == pytest.approx(np.log(101.0 / 100.0))


def test_seasonality_profile_shape():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-06-01", periods=24 * 30, freq="1h", tz="UTC")
    scale = np.where(idx.hour == 12, 3.0, 1.0)       # UTC12だけ高ボラ
    lr = pd.Series(rng.standard_normal(len(idx)) * 0.001 * scale, index=idx)
    prof = empirical.seasonality_profile(lr)
    assert len(prof) == 24
    top = prof.loc[prof["vol_factor"].idxmax()]
    assert top["utc_hour"] == 12 and top["vol_factor"] > 2.0
