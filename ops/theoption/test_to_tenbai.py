# -*- coding: utf-8 -*-
"""to_tenbai の安全装置と解析のテスト(ネットワーク不要): python -m pytest -q test_to_tenbai.py"""
import base64, json
import to_tenbai as T

def jwt(payload):
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return e(b'{"alg":"HS256"}') + "." + e(json.dumps(payload).encode()) + ".sig"

def test_demo_key_guard():
    assert T.is_demo_key(jwt({"iss": "TheOptionDemo", "uid": "1"}))
    assert not T.is_demo_key(jwt({"iss": "TheOption", "uid": "1"}))
    assert not T.is_demo_key("not-a-jwt") and T.jwt_iss("") is None

def test_hosts_are_demo_only_and_never_trades():
    assert "apidemo." in T.BASE and "gatewaydemo." in T.WSS and "api.theoption.com/" not in T.BASE
    src = open(T.__file__, encoding="utf-8").read()
    assert "/trading/buy" not in src and "/trading/sell" not in src

def test_deep_find_in_nested_json_strings():
    fr = {"type": "update", "key": "254900", "values": {"trade": json.dumps({"x": 1}), "sell": json.dumps({"can_sell": True, "price": 412})}}
    assert T.deep_find(fr, "can_sell") is True and T.deep_find(fr, "price") == 412 and T.deep_find(fr, "nope") is None

def test_snapshot_joins_trade_rows_with_contract_data():
    trade = {"type": "update", "key": "254900", "values": {
        "trade": json.dumps({"contract": "AUDJPY|FE|23H|HIGHLOW|HIGH", "strike": 110.050}),
        "sell": json.dumps({"can_sell": True, "sell_price": 380})}}
    cd = {"type": "update", "stream": "contract_data", "key": "AUDJPY|FE|23H|HIGHLOW|HIGH|2026_10_26_21_00_00",
          "values": {"asset": json.dumps({"rate": 109.930, "timestamp": "x"})}}
    s = T.snapshot([{"type": "ready"}, trade, cd])
    assert list(s) == ["254900"] and s["254900"]["contract"] == "AUDJPY|FE|23H|HIGHLOW|HIGH"
    assert s["254900"]["can_sell"] is True and abs(s["254900"]["depth_pip"] - (-12.0)) < 1e-6
