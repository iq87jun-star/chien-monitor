# -*- coding: utf-8 -*-
"""to_live の安全装置と契約選択のテスト(ネットワーク不要): python -m pytest -q test_to_live.py"""
import base64, json, datetime as dt, os, tempfile
import to_live as L

def jwt(payload):
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return e(b'{"alg":"HS256"}') + "." + e(json.dumps(payload).encode()) + ".sig"

DEMO = jwt({"iss": "TheOptionDemo"}); REAL = jwt({"iss": "TheOption"})
MON = dt.date(2026, 10, 26)

def test_menu_matches_readme_addendum31_and_34():
    assert len(L.MENU) == 8 and sum(l["stake"] for l in L.MENU) == 98500
    assert sum(l["stake"] for l in L.MENU if l["entry"] == "07:00") == 62700          # 月曜 07:00 の 23H × 3(DD40万換算)
    mon = sum(l["stake"] for l in L.MENU if 0 in l["wds"] and not l.get("gotobi")); assert mon == 72700 and mon * L.BOOST_MULT <= L.DAILY_STAKE_CAP
    nk = [l for l in L.MENU if l.get("gotobi")]
    assert [l["pair"] for l in nk] == ["USDJPY", "EURJPY", "GBPJPY"] and all(l["kind"] == "15M" and l["sel"] == "LOW" and l["entry"] == "09:55" and l["judge"] == "10:10" and not l["next"] and l["stake"] == 7000 for l in nk)
    assert mon + sum(l["stake"] for l in nk) <= L.DAILY_STAKE_CAP                      # 月曜がゴトー日でも日次上限内(93,700)
    assert all(l["kind"] == "23H" and l["judge"] == "06:00" for l in L.MENU if not l.get("gotobi"))
    assert all((not l["next"]) == (l["entry"] < "06:00") for l in L.MENU if not l.get("gotobi"))      # 深夜建て(02:00)だけ同日判定
    assert all(l["stake"] <= L.MAX_STAKE for l in L.MENU) and len({l["id"] for l in L.MENU}) == 8

def test_jp_bank_holidays_and_gotobi():
    H = L.jp_bank_holidays(2026)
    assert dt.date(2026, 1, 12) in H and dt.date(2026, 7, 20) in H and dt.date(2026, 9, 21) in H and dt.date(2026, 10, 12) in H   # ハッピーマンデー
    assert dt.date(2026, 3, 20) in H and dt.date(2026, 9, 23) in H                                   # 春分・秋分
    assert dt.date(2026, 5, 6) in H and dt.date(2026, 11, 23) in H and dt.date(2026, 12, 31) in H    # 振替(5/3 日曜→5/6)・勤労感謝・大晦日
    assert dt.date(2026, 9, 22) in H                                                                 # 国民の休日(敬老 9/21 と秋分 9/23 の間)
    assert dt.date(2021, 7, 22) in L.jp_bank_holidays(2021) and dt.date(2021, 7, 19) not in L.jp_bank_holidays(2021)   # 五輪特例
    g = L.gotobi_days(2026)
    assert dt.date(2026, 11, 5) in g and dt.date(2026, 11, 10) in g and dt.date(2026, 11, 13) in g and dt.date(2026, 11, 15) not in g   # 11/15 日曜→11/13 金曜
    assert dt.date(2026, 11, 20) in g and dt.date(2026, 11, 25) in g and dt.date(2026, 11, 30) in g
    assert dt.date(2026, 5, 1) in g and dt.date(2026, 5, 5) not in g                 # 5/5 祝日・5/4 祝日・5/3 日曜・5/2 土曜 → 5/1 金曜
    assert dt.date(2026, 12, 30) in g and dt.date(2026, 12, 31) not in g             # 大晦日は銀行休業 → 12/30
    assert dt.date(2027, 1, 5) in L.gotobi_days(2027) and L.is_gotobi(dt.date(2026, 11, 5)) and not L.is_gotobi(dt.date(2026, 11, 4))
    assert dt.date(2026, 11, 2) not in g                                              # 11/2(月)はゴトー日ではない

def test_due_legs_by_weekday_and_month():
    assert [l["id"] for l in L.MENU if L.is_due_today(l, MON)] == ["EURJPY_N6", "AUDJPY_N6", "NZDJPY_N6", "EURGBP_N6L"]   # 10 月の月曜(10/26 はゴトー日でない)
    tue = dt.date(2026, 10, 27); assert [l["id"] for l in L.MENU if L.is_due_today(l, tue)] == ["EURGBP_N6L", "AUDJPY_02"]
    wed = dt.date(2026, 10, 28); assert [l["id"] for l in L.MENU if L.is_due_today(l, wed)] == ["EURGBP_N6L", "AUDJPY_02"]
    thu = dt.date(2026, 10, 29); assert [l["id"] for l in L.MENU if L.is_due_today(l, thu)] == ["AUDJPY_02"]
    fri = dt.date(2026, 10, 30); assert [l["id"] for l in L.MENU if L.is_due_today(l, fri)] == ["EURGBP_N6L", "AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK"]   # 10/30 = 月末(ゴトー日)
    nov5 = dt.date(2026, 11, 5); assert [l["id"] for l in L.MENU if L.is_due_today(l, nov5)] == ["AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK"]
    nov10 = dt.date(2026, 11, 10); assert [l["id"] for l in L.MENU if L.is_due_today(l, nov10)] == ["EURGBP_N6L", "AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK"]
    jun_mon = dt.date(2026, 6, 1); assert "EURGBP_N6L" not in [l["id"] for l in L.MENU if L.is_due_today(l, jun_mon)]

def test_slot_selection_around_entry_time():
    now = dt.datetime(2026, 10, 26, 6, 58, tzinfo=L.JST)
    assert {l["entry"] for l in L.legs_for_slot(now)} == {"07:00"} and len(L.legs_for_slot(now)) == 3
    now = dt.datetime(2026, 10, 26, 9, 58, tzinfo=L.JST); assert L.legs_for_slot(now) == []           # v1.4: 月曜 10:00 以降の分割脚は無い(タスクは空振りで無害)
    now = dt.datetime(2026, 10, 26, 9, 54, tzinfo=L.JST); assert L.legs_for_slot(now) == []           # 10/26 はゴトー日でない → 09:54 起動は空振り
    now = dt.datetime(2026, 11, 5, 9, 54, tzinfo=L.JST); legs = L.legs_for_slot(now)                  # 11/5(木)ゴトー日 → 仲値 3 本
    assert [l["id"] for l in legs] == ["USDJPY_NK", "EURJPY_NK", "GBPJPY_NK"] and all(l["_day"] == dt.date(2026, 11, 5) for l in legs)
    assert L.judge_utc(legs[0], legs[0]["_day"]) == dt.datetime(2026, 11, 5, 1, 10, tzinfo=L.UTC)
    now = dt.datetime(2026, 10, 26, 22, 58, tzinfo=L.JST); assert [l["id"] for l in L.legs_for_slot(now)] == ["EURGBP_N6L"]
    now = dt.datetime(2026, 10, 29, 22, 58, tzinfo=L.JST); assert L.legs_for_slot(now) == []          # 木曜 23:00 は EURGBP 対象外
    assert all(l["_day"] == MON for l in L.legs_for_slot(dt.datetime(2026, 10, 26, 6, 58, tzinfo=L.JST)))

def test_slot_crossing_midnight_uses_next_day():
    now = dt.datetime(2026, 10, 26, 23, 58, tzinfo=L.JST)   # 月 23:58 起動 → 火 00:00 には脚が無い(v1.4)
    assert L.legs_for_slot(now) == []
    for d in (27, 28, 29, 30):   # 火〜金 01:58 起動 → 02:00 建ての AUDJPY_02、建てる日はその日
        legs = L.legs_for_slot(dt.datetime(2026, 10, d, 1, 58, tzinfo=L.JST))
        assert [l["id"] for l in legs] == ["AUDJPY_02"] and legs[0]["_day"] == dt.date(2026, 10, d)
    legs = L.legs_for_slot(dt.datetime(2026, 10, 27, 1, 58, tzinfo=L.JST))
    assert L.judge_utc(legs[0], legs[0]["_day"]) == dt.datetime(2026, 10, 26, 21, 0, tzinfo=L.UTC)   # 火 06:00 JST
    assert L.legs_for_slot(dt.datetime(2026, 10, 26, 1, 58, tzinfo=L.JST)) == []   # 月 02:00 には無い(日曜セッションは無い)
    assert L.legs_for_slot(dt.datetime(2026, 10, 31, 1, 58, tzinfo=L.JST)) == []   # 土 02:00 には無い

def test_judge_time_utc():
    leg = next(l for l in L.MENU if l["id"] == "EURJPY_N6"); assert L.judge_utc(leg, MON) == dt.datetime(2026, 10, 26, 21, 0, tzinfo=L.UTC)   # 月 07:00 建て→火 06:00
    leg = next(l for l in L.MENU if l["id"] == "AUDJPY_02"); assert L.judge_utc(leg, dt.date(2026, 10, 27)) == dt.datetime(2026, 10, 26, 21, 0, tzinfo=L.UTC)   # 火 02:00 建て→火 06:00(同日)

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
    leg14 = dict(id="GBPJPY_14", pair="GBPJPY", sel="HIGH", entry="07:00", judge="14:00", next=False, stake=1000, wds=[0], months=None, kind="23H")
    assert L.pick_contract(frames, leg14, MON)["name"] == "GBPJPY|FE|7H|HIGHLOW|HIGH"   # 期間ラベルが未知でも判定時刻で拾う
    leg = next(l for l in L.MENU if l["id"] == "AUDJPY_N6"); assert L.pick_contract(frames, leg, MON) is None   # 無い脚は None → 見送り

def test_pick_15m_contract_allows_prescan_status():
    nk = next(l for l in L.MENU if l["id"] == "USDJPY_NK"); day = dt.date(2026, 11, 5)
    frames = [upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:10:00.000Z", "1.85", status="Unknown"),
              upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85", status="Open"),
              upd("USDJPY|FE|15M|HIGHLOW|HIGH", "2026-11-05T01:10:00.000Z", "1.85", status="Unknown"),
              upd("USDJPY|FE|1H|HIGHLOW|LOW", "2026-11-05T02:00:00.000Z", "1.9"),
              upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:10:00.000Z", "1.85", status="Closed")]
    c = L.pick_contract(frames[:4], nk, day); assert c and c["name"] == "USDJPY|FE|15M|HIGHLOW|LOW" and c["expiration_time"] == "2026-11-05T01:10:00.000Z"
    assert L.pick_contract([frames[4]], nk, day) is None                                  # Closed は選ばない
    n6 = next(l for l in L.MENU if l["id"] == "EURJPY_N6")                                # 23H 脚は従来どおり Open のみ
    assert L.pick_contract([upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z", status="Unknown")], n6, MON) is None
    assert L.stake_for(nk, "1.85") == 7000 and L.stake_for(nk, "1.80") == 0 and L.stake_for(nk, "2.0") == 10500

def test_run_entries_fast_path_for_15m(monkeypatch):
    calls = []; sleeps = []
    def fake_rest(base, path, key, body=None, timeout=15):
        calls.append((path, body, timeout))
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 200000}}
        if path == "/trading/buy":
            if len([c for c in calls if c[0] == "/trading/buy"]) == 1: return 200, {"status": "fail", "errors": [{"errorCode": 300}]}   # 1 本目は未開場で拒否→再試行
            return 200, {"status": "success", "data": {"trade": 7, "order_properties": {"strike": 153.21}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest); monkeypatch.setattr(L, "sleep_until", lambda t: sleeps.append(t)); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    scans = []
    async def fake_scan(wss, key, secs):
        scans.append(secs)
        return [upd(f"{p}|FE|15M|HIGHLOW|LOW", "2026-11-05T01:10:00.000Z", "1.85", status="Unknown") for p in ("USDJPY", "EURJPY", "GBPJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        now = dt.datetime(2026, 11, 5, 9, 54, tzinfo=L.JST)
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0
        e = dt.datetime(2026, 11, 5, 9, 55, tzinfo=L.JST)
        assert sleeps == [e - dt.timedelta(seconds=25), e + dt.timedelta(seconds=1)] and scans == [24]   # 先読み → 定刻 +1 秒に発注
        buys = [c for c in calls if c[0] == "/trading/buy"]; assert len(buys) == 4 and all(c[2] == 8 for c in buys)   # 拒否 1 回 + 成功 3 本
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 4 and all(",7000,7,153.21," in r for r in rows[1:]) and rows[1].startswith("2026-11-05,USDJPY_NK,USDJPY,LOW,1.85,7000")

def test_payout_rule():
    leg1h = dict(id="X_1H", pair="AUDJPY", sel="HIGH", entry="08:00", judge="09:00", next=False, stake=8000, wds=[0], months=None, kind="1H")
    leg23 = next(l for l in L.MENU if l["kind"] == "23H")
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

def test_config_with_bom_is_read(monkeypatch):
    # to_setup.ps1(PS 5.1 の Set-Content -Encoding UTF8)が書く BOM 付き to_config.json でも live_real を読めること
    monkeypatch.setenv("THEOPTION_API_KEY", DEMO); monkeypatch.setenv("THEOPTION_API_KEY_REAL", REAL)
    monkeypatch.setattr(L, "HERE", tempfile.mkdtemp())
    with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x", "live_real": True}, f)
    assert L.load_account("x") == ("real", REAL)
    with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x"}, f)
    assert L.load_account("x")[0] == "demo"

def test_run_entries_skips_missing_contract_and_records_csv(monkeypatch):
    calls = []
    def fake_rest(base, path, key, body=None, timeout=15):
        calls.append((path, body))
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 200000}}
        if path == "/trading/buy": return 200, {"status": "success", "data": {"trade": 1, "order_properties": {"strike": 176.1}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest); monkeypatch.setattr(L, "sleep_until", lambda t: None); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    frames = [upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-10-26T21:00:00.000Z", "1.95")]
    async def fake_scan(wss, key, secs): return frames
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        now = dt.datetime(2026, 10, 26, 6, 58, tzinfo=L.JST)   # 月曜 07:00: 3 本のうち EURJPY だけ契約がある → 1 本購入・2 本「契約なし」
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 4 and rows[1].startswith("2026-10-26,EURJPY_N6,EURJPY,HIGH,1.95,21300,1,176.1,EURJPY|FE|23H|HIGHLOW|HIGH")
        assert rows[2].startswith("2026-10-26,AUDJPY_N6,AUDJPY,HIGH,,0,") and rows[3].startswith("2026-10-26,NZDJPY_N6,NZDJPY,HIGH,,0,")
        assert [p for p, _ in calls] == ["/trading/health", "/wallet/balance", "/trading/buy"]
        # 同じ日に再実行しても二重発注しない
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0 and [p for p, _ in calls].count("/trading/buy") == 1
