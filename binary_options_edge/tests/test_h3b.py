"""H3b(発表後ボラ崩壊)フィルタとprev_event_secondsのテスト。"""
from datetime import datetime, timedelta, timezone

from binary_options_edge.data import CalendarEvent, CalendarSource
from binary_options_edge.hypotheses import Context, h3b_post_event


class OneEventCalendar(CalendarSource):
    def __init__(self, t):
        self.t = t

    def events(self, start, end):
        e = CalendarEvent(time=self.t, pair_relevance=("USDJPY",),
                          name="NFP", importance=3)
        return [e] if start <= self.t <= end else []


def _ctx(prev):
    return Context(0.1, 0.1, None, 12, 0.0, prev)


def test_h3b_fires_only_in_post_event_window():
    f = h3b_post_event(window_seconds=1800.0, min_after_seconds=300.0)
    assert not f(None, _ctx(None))       # イベント無し→保守的にFalse
    assert not f(None, _ctx(60.0))       # 発表1分後: まだ早い(スパイク中)
    assert f(None, _ctx(600.0))          # 発表10分後: 窓内
    assert not f(None, _ctx(3600.0))     # 発表60分後: 窓外


def test_prev_event_seconds():
    t_ev = datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc)
    cal = OneEventCalendar(t_ev)
    assert cal.prev_event_seconds("USDJPY", t_ev + timedelta(minutes=10)) == 600.0
    assert cal.prev_event_seconds("USDJPY", t_ev - timedelta(minutes=10)) is None
    assert cal.prev_event_seconds("EURUSD", t_ev + timedelta(minutes=10)) is None
