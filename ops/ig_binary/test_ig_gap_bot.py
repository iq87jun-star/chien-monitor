# -*- coding: utf-8 -*-
"""オフライン検証: python -m pytest ops/ig_binary -q(ネットワーク・秘密なし)。"""
import datetime as dt, os, sys, tempfile, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ig_gap_bot as B

UTC = dt.timezone.utc
MON = dt.date(2026, 10, 12)

def test_key_times():
    e, x = B.key_times(MON)
    assert e == dt.datetime(2026, 10, 11, 22, 0, tzinfo=UTC) and x == dt.datetime(2026, 10, 12, 0, 0, tzinfo=UTC)

def test_decide_gap_down_only():
    assert B.decide("USDJPY", 150.00, 149.80, {}) == ("HIGH", -20.0)
    assert B.decide("USDJPY", 150.00, 150.10, {})[0] is None
    assert B.decide("EURUSD", 1.1000, 1.1000, {})[0] is None
    assert B.decide("EURUSD", 1.1000, 1.0998, {"min_gap_pips": 3})[0] is None      # 2 pips < 3
    assert B.decide("EURUSD", 1.1000, 1.0995, {"min_gap_pips": 3}) == ("HIGH", -5.0)

def test_max_filled():
    assert abs(B.filled_ratio(150.0, 149.8, 149.9) - 0.5) < 1e-9 and abs(B.filled_ratio(150.0, 149.8, 149.7) + 0.5) < 1e-9
    assert B.decide("USDJPY", 150.0, 149.8, {}, 149.85)[0] == "HIGH"                  # 25% 埋め → 買う
    assert B.decide("USDJPY", 150.0, 149.8, {}, 149.92)[0] is None                    # 60% 埋め → 見送り
    assert B.decide("USDJPY", 150.0, 149.8, {}, 149.70)[0] == "HIGH"                  # さらに広げた → 買う
    assert B.decide("USDJPY", 150.0, 149.8, {"max_filled": None}, 149.92)[0] == "HIGH" # 無効化

def test_outcome_and_pnl():
    assert B.outcome(1.0, 1.1) == "win" and B.outcome(1.0, 0.9) == "lose" and B.outcome(1.0, 1.0) == "draw" and B.outcome(1.0, None) is None
    assert B.pnl_virtual("win", 20000, 0.55) == 16364 and B.pnl_virtual("lose", 20000, 0.55) == -20000 and B.pnl_virtual("draw", 20000, 0.55) == 0

def _bars(fri_close, mon_first, entry, exit_):
    e, x = B.key_times(MON)
    return [(dt.datetime(2026, 10, 9, 20, 59, tzinfo=UTC), fri_close + 0.01, fri_close),
            (dt.datetime(2026, 10, 11, 21, 5, tzinfo=UTC), mon_first, mon_first),          # 夏時間型: 開場 1 時間前に最初の値
            (e, entry, entry), (e + dt.timedelta(minutes=1), entry, entry),
            (x, exit_, exit_)]

def test_weekend_gap_and_price_at():
    b = _bars(150.0, 149.8, 149.85, 150.1); e, x = B.key_times(MON)
    assert B.weekend_gap(b, e) == (150.0, 149.8) and B.price_at(b, e) == 149.85 and B.price_at(b, x) == 150.1
    assert B.weekend_gap(b[2:], e) is None                                             # 金曜の値が無い

class Fake:
    name = "dukascopy"
    def __init__(self, data): self.data = data
    def bars(self, pair, start, end): return [b for b in self.data.get(pair, []) if start <= b[0] <= end]

def test_signal_settle_report_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = dict(transport="dry", pairs=["USDJPY", "EURUSD", "GBPJPY"], stake=20000, breakeven=0.55, retries=1,
                   log_csv=os.path.join(tmp, "log.csv"), state_json=os.path.join(tmp, "state.json"))
        src = [Fake({"USDJPY": _bars(150.0, 149.8, 149.85, 150.1),      # 下窓 → HIGH → 勝ち
                     "GBPJPY": _bars(200.0, 199.5, 199.6, 199.4),       # 下窓 → HIGH → 負け
                     "EURUSD": _bars(1.10, 1.1005, 1.1004, 1.1010)})]   # 上窓 → 見送り
        st = B.State(cfg["state_json"])
        B.do_signal(cfg, MON, st, dry=True, sources=src)
        p = st.d[MON.isoformat()]["pairs"]
        assert p["USDJPY"]["signal"] == "HIGH" and p["GBPJPY"]["signal"] == "HIGH" and p["EURUSD"]["signal"] is None
        B.do_signal(cfg, MON, st, dry=True, sources=src)                # 二重実行しない
        B.do_settle(cfg, MON, st, dry=True, sources=src)
        assert st.d[MON.isoformat()]["pnl_virtual"] == 16364 - 20000
        rows = list(csv.DictReader(open(cfg["log_csv"], encoding="utf-8")))
        assert len(rows) == 3 and {r["pair"]: r["result"] for r in rows} == {"USDJPY": "win", "GBPJPY": "lose", "EURUSD": ""}
        B.do_settle(cfg, MON, st, dry=True, sources=src)                # 二重決済しない
        assert len(list(csv.DictReader(open(cfg["log_csv"], encoding="utf-8")))) == 3
        s = B.summarize(rows, 0.55, 20000)
        assert s["n"] == 2 and s["wins"] == 1 and s["pnl_virtual"] == -3636 and "ig_n" not in s

def test_summarize_with_ig_premium():
    rows = [dict(signal="HIGH", result="win", pnl_virtual="16364", ig_premium="600"),
            dict(signal="HIGH", result="lose", pnl_virtual="-20000", ig_premium="500"),
            dict(signal="HIGH", result="win", pnl_virtual="16364", ig_premium="")]
    s = B.summarize(rows, 0.55, 20000)
    assert s["n"] == 3 and s["ig_n"] == 2 and s["ig_breakeven"] == 0.55
    assert s["ig_pnl"] == round(400 * 20000 / 600) - 20000                     # 実購入価格 600 円なら勝ちは +13,333 円
