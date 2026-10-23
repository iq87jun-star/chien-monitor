# -*- coding: utf-8 -*-
"""to_tenbai の安全装置と解析のテスト(ネットワーク不要): python -m pytest -q test_to_tenbai.py"""
import base64, json, datetime as dt, os, tempfile
import to_tenbai as T

def jwt(payload):
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return e(b'{"alg":"HS256"}') + "." + e(json.dumps(payload).encode()) + ".sig"

DEMO = jwt({"iss": "TheOptionDemo", "uid": "1"}); REAL = jwt({"iss": "TheOption", "uid": "1"})

def test_demo_key_guard():
    assert T.is_demo_key(DEMO) and not T.is_demo_key(REAL)
    assert not T.is_demo_key("not-a-jwt") and T.jwt_iss("") is None

def test_hosts_are_demo_only():
    assert "apidemo." in T.BASE and "gatewaydemo." in T.WSS
    src = open(T.__file__, encoding="utf-8").read()
    assert "api.theoption.com/v1" not in src.replace("apidemo.theoption.com/v1", "") and "gateway.theoption.com" not in src.replace("gatewaydemo.", "")

def test_buy_body_matches_quickstart():
    b = T.buy_body("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-27T21:00:00.000Z")
    assert b == {"contract": "EURJPY|FE|23H|HIGHLOW|HIGH", "amount": 1000, "order_type": "market",
                 "order_properties": {"expiration_time": "2026-10-27T21:00:00.000Z"}}
    assert T.AMOUNT == 1000 and T.MAX_BUYS == 3

def test_pick_contracts_from_frames():
    now = dt.datetime(2026, 10, 25, 22, 0, tzinfo=dt.timezone.utc)   # 月曜 07:00 JST
    def upd(name, exp, status="Open"):
        return {"type": "update", "key": name + "|x", "values": {"contract": json.dumps({"name": name, "status": status, "expiration_time": exp})}}
    frames = [upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z"),      # 翌 06:00 JST → 採用
              upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-25T21:00:00.000Z"),      # 当日 06:00(過去)→ 除外
              upd("AUDJPY|FE|23H|HIGHLOW|LOW",  "2026-10-26T21:00:00.000Z"),      # LOW → 対象外
              upd("NZDJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z", "Cut Off")]
    assert T.pick_contracts(frames, now) == {"EURJPY": ("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z")}

def test_contracts_from_probe_jsonl_reads_same_day_file():
    now = dt.datetime.now(dt.timezone.utc); exp = (now + dt.timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    with tempfile.TemporaryDirectory() as tmp:
        today = dt.datetime.now(T.JST).strftime("%Y%m%d")
        with open(os.path.join(tmp, f"probe_demo_{today}_0525.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "ws", "frame": {"type": "update", "key": "AUDJPY|FE|23H|HIGHLOW|HIGH|x",
                                "values": {"contract": json.dumps({"name": "AUDJPY|FE|23H|HIGHLOW|HIGH", "status": "Open", "expiration_time": exp})}}}) + "\n")
        assert T.contracts_from_probe_jsonl(tmp, now) == {"AUDJPY": ("AUDJPY|FE|23H|HIGHLOW|HIGH", exp)}

def test_deep_find_and_snapshot():
    trade = {"type": "update", "key": "254900", "values": {
        "trade": json.dumps({"contract": "AUDJPY|FE|23H|HIGHLOW|HIGH", "strike": 110.050}),
        "sell": json.dumps({"can_sell": True, "sell_price": 380})}}
    cd = {"type": "update", "stream": "contract_data", "key": "AUDJPY|FE|23H|HIGHLOW|HIGH|2026_10_26_21_00_00",
          "values": {"asset": json.dumps({"rate": 109.930, "timestamp": "x"})}}
    s = T.snapshot([{"type": "ready"}, trade, cd])
    assert list(s) == ["254900"] and s["254900"]["can_sell"] is True and abs(s["254900"]["depth_pip"] - (-12.0)) < 1e-6
    assert T.deep_find(trade, "nope") is None

def test_try_sell_one_picks_underwater_only(monkeypatch):
    calls = []
    monkeypatch.setattr(T, "rest", lambda path, key, body=None, timeout=15: (calls.append((path, body)), (200, {"status": "success", "data": {}}))[1])
    trades = [{"pair": "NZDJPY", "trade": "1"}, {"pair": "AUDJPY", "trade": "2"}, {"pair": "EURJPY", "trade": "3"}]
    snap = {"1": {"depth_pip": +3.0, "can_sell": True, "sell": None}, "2": {"depth_pip": -8.0, "can_sell": False, "sell": None}, "3": {"depth_pip": -5.0, "can_sell": True, "sell": None}}
    with tempfile.TemporaryDirectory() as tmp:
        r = T.try_sell_one("k", snap, trades, T.Log(os.path.join(tmp, "x.jsonl")))
    assert r["pair"] == "EURJPY" and calls == [("/trading/sell", {"tradeActionID": 3})]

def test_main_refuses_real_key_without_any_call(monkeypatch):
    calls = []
    monkeypatch.setattr(T, "rest", lambda *a, **k: (calls.append(a), (200, {}))[1])
    monkeypatch.setenv("THEOPTION_API_KEY", REAL)
    with tempfile.TemporaryDirectory() as tmp:
        assert T.main(["--live-demo", "--out", tmp]) == 3
    assert calls == []

def test_main_without_live_demo_never_buys(monkeypatch):
    calls = []
    def fake_rest(path, key, body=None, timeout=15):
        calls.append(path); return 200, {"status": "success", "data": {"isActive": True, "balance": 50000, "results": []}}
    monkeypatch.setattr(T, "rest", fake_rest)
    async def fake_ws(key, names, secs, want_contracts=False): return [{"type": "ready"}]
    monkeypatch.setattr(T, "ws_collect", fake_ws)
    monkeypatch.setenv("THEOPTION_API_KEY", DEMO)
    with tempfile.TemporaryDirectory() as tmp:
        assert T.main(["--once", "--out", tmp]) == 0
        assert os.path.exists(os.path.join(tmp, "_diag", "tenbai_last_run.txt"))
    assert "/trading/buy" not in calls and "/trading/sell" not in calls and "/trading/health" in calls
