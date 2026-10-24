# -*- coding: utf-8 -*-
"""to_live の安全装置と契約選択のテスト(ネットワーク不要): python -m pytest -q test_to_live.py"""
import base64, json, datetime as dt, os, tempfile
import to_live as L

def jwt(payload):
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return e(b'{"alg":"HS256"}') + "." + e(json.dumps(payload).encode()) + ".sig"

DEMO = jwt({"iss": "TheOptionDemo"}); REAL = jwt({"iss": "TheOption"})
MON = dt.date(2026, 10, 26)

def test_menu_matches_readme_addendum18():
    assert len(L.MENU) == 10 and sum(l["stake"] for l in L.MENU) == 88500
    assert sum(l["stake"] for l in L.MENU if l["entry"] == "07:00") == 70500   # 月曜 07:00 の 8 本
    assert all(l["stake"] <= L.MAX_STAKE for l in L.MENU)

def test_due_legs_by_weekday_and_month():
    assert [l["id"] for l in L.MENU if L.is_due_today(l, MON)] == [l["id"] for l in L.MENU]          # 10 月の月曜: 10 本
    tue = dt.date(2026, 10, 27); assert [l["id"] for l in L.MENU if L.is_due_today(l, tue)] == ["EURGBP_N6L"]
    thu = dt.date(2026, 10, 29); assert [l["id"] for l in L.MENU if L.is_due_today(l, thu)] == []
    jun_mon = dt.date(2026, 6, 1); assert "EURGBP_N6L" not in [l["id"] for l in L.MENU if L.is_due_today(l, jun_mon)]

def test_slot_selection_around_entry_time():
    now = dt.datetime(2026, 10, 26, 6, 58, tzinfo=L.JST)
    assert {l["entry"] for l in L.legs_for_slot(now)} == {"07:00"} and len(L.legs_for_slot(now)) == 8
    now = dt.datetime(2026, 10, 26, 10, 58, tzinfo=L.JST); assert [l["id"] for l in L.legs_for_slot(now)] == ["AUDJPY_11N10"]
    now = dt.datetime(2026, 10, 26, 22, 58, tzinfo=L.JST); assert [l["id"] for l in L.legs_for_slot(now)] == ["EURGBP_N6L"]
    now = dt.datetime(2026, 10, 26, 9, 0, tzinfo=L.JST); assert L.legs_for_slot(now) == []

def test_judge_time_utc():
    leg = next(l for l in L.MENU if l["id"] == "EURJPY_N6"); assert L.judge_utc(leg, MON) == dt.datetime(2026, 10, 26, 21, 0, tzinfo=L.UTC)
    leg = next(l for l in L.MENU if l["id"] == "GBPJPY_1H"); assert L.judge_utc(leg, MON) == dt.datetime(2026, 10, 25, 23, 0, tzinfo=L.UTC)
    leg = next(l for l in L.MENU if l["id"] == "AUDJPY_11N10"); assert L.judge_utc(leg, MON) == dt.datetime(2026, 10, 27, 1, 0, tzinfo=L.UTC)

def upd(name, exp, payout="1.95", status="Open"):
    return {"type": "update", "key": name + "|x", "values": {"contract": json.dumps({"name": name, "status": status, "expiration_time": exp, "payout_multiplier": payout})}}

def test_pick_contract_by_pair_selection_and_judge_time():
    frames = [upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z"),
              upd("EURJPY|FE|23H|HIGHLOW|LOW",  "2026-10-26T21:00:00.000Z"),
              upd("EURJPY|FE|22H|HIGHLOW|HIGH", "2026-10-26T20:00:00.000Z"),
              upd("EURJPY|FE|23H|SPREAD|HIGH",  "2026-10-26T21:00:00.000Z", "2.0"),
              upd("GBPJPY|FE|1H|HIGHLOW|HIGH",  "2026-10-25T23:00:00.000Z", "1.9"),
              upd("GBPJPY|FE|7H|HIGHLOW|HIGH",  "2026-10-26T05:00:00.000Z", "1.95")]   # 期間ラベルが未知でも判定時刻で拾う
    leg = next(l for l in L.MENU if l["id"] == "EURJPY_N6"); c = L.pick_contract(frames, leg, MON)
    assert c["name"] == "EURJPY|FE|23H|HIGHLOW|HIGH" and c["payout"] == "1.95"
    leg = next(l for l in L.MENU if l["id"] == "GBPJPY_14"); assert L.pick_contract(frames, leg, MON)["name"] == "GBPJPY|FE|7H|HIGHLOW|HIGH"
    leg = next(l for l in L.MENU if l["id"] == "AUDJPY_N6"); assert L.pick_contract(frames, leg, MON) is None   # 無い脚は None → 見送り

def test_payout_rule():
    leg1h = next(l for l in L.MENU if l["kind"] == "1H"); leg23 = next(l for l in L.MENU if l["kind"] == "23H")
    assert L.stake_for(leg1h, "1.9") == leg1h["stake"] and L.stake_for(leg1h, "1.84") == 0
    assert L.stake_for(leg23, "1.95") == leg23["stake"] and L.stake_for(leg23, "1.89") == 0
    assert L.stake_for(leg23, "2.0") == int(leg23["stake"] * 1.5) and L.stake_for(leg23, None) == 0

def test_buy_body_and_account_guards():
    assert L.buy_body("X|FE|1H|HIGHLOW|HIGH", "2026-10-25T23:00:00.000Z", 10500) == {"contract": "X|FE|1H|HIGHLOW|HIGH", "amount": 10500, "order_type": "market", "order_properties": {"expiration_time": "2026-10-25T23:00:00.000Z"}}
    assert L.key_matches_account("demo", DEMO) and not L.key_matches_account("demo", REAL)
    assert L.key_matches_account("real", REAL) and not L.key_matches_account("real", DEMO) and not L.key_matches_account("real", "junk")

def test_default_account_is_demo_without_double_opt_in(monkeypatch):
    monkeypatch.setenv("THEOPTION_API_KEY", DEMO); monkeypatch.setenv("THEOPTION_API_KEY_REAL", REAL)
    monkeypatch.setattr(L, "HERE", tempfile.mkdtemp())      # to_config.json 無し → お試し
    assert L.load_account("x")[0] == "demo"
    with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8") as f: json.dump({"out": "x", "live_real": True}, f)
    assert L.load_account("x") == ("real", REAL)
    monkeypatch.delenv("THEOPTION_API_KEY_REAL"); assert L.load_account("x")[0] == "demo"

def test_run_entries_skips_missing_contract_and_records_csv(monkeypatch):
    calls = []
    def fake_rest(base, path, key, body=None, timeout=15):
        calls.append((path, body))
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 50000}}
        if path == "/trading/buy": return 200, {"status": "success", "data": {"trade": 1, "order_properties": {"strike": 176.1}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest); monkeypatch.setattr(L, "sleep_until", lambda t: None); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    frames = [upd("EURGBP|FE|23H|HIGHLOW|LOW", "2026-10-26T21:00:00.000Z", "1.95")]
    async def fake_scan(wss, key, secs): return frames
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        now = dt.datetime(2026, 10, 26, 22, 58, tzinfo=L.JST)   # 月曜 23:00 の EURGBP だけが対象
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 2 and rows[1].startswith("2026-10-26,EURGBP_N6L,EURGBP,LOW,1.95,5000,1,176.1,EURGBP|FE|23H|HIGHLOW|LOW")
        assert [p for p, _ in calls] == ["/trading/health", "/wallet/balance", "/trading/buy"]
        # 同じ日に再実行しても二重発注しない
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0 and [p for p, _ in calls].count("/trading/buy") == 1
