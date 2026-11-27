# -*- coding: utf-8 -*-
"""to_live の安全装置と契約選択のテスト(ネットワーク不要): python -m pytest -q test_to_live.py"""
import base64, json, datetime as dt, os, tempfile
import pytest
import to_live as L

@pytest.fixture(autouse=True)
def _no_network_skew(monkeypatch):   # v1.11: テストは CBOE へ取りに行かない(取得失敗 = 記録に error、発注は続く)
    def boom(timeout=12): raise OSError("offline")
    monkeypatch.setattr(L, "fetch_skew_csv", boom)
    monkeypatch.setattr(L, "snap_rates_sync", lambda wss, key, pairs, secs: {})   # v1.12: レート記録もネットワーク無し
    def boom2(pair, timeout=12): raise OSError("offline")
    monkeypatch.setattr(L, "fetch_hourly", boom2)   # v1.17: 金曜の騰落の記録もネットワーク無し
    monkeypatch.setattr(L, "STAKE_SCALE", 1.0)        # v1.18: 既存のテストは基準額(倍率 1.0)で確かめる。倍率は test_v118_* で確認
    def boom3(timeout=12): raise OSError("offline")
    monkeypatch.setattr(L, "fetch_spx_daily", boom3)  # v1.18: S&P500 もネットワーク無し(取得失敗 = 月末脚は見送り)

def jwt(payload):
    e = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return e(b'{"alg":"HS256"}') + "." + e(json.dumps(payload).encode()) + ".sig"

DEMO = jwt({"iss": "TheOptionDemo"}); REAL = jwt({"iss": "TheOption"})
MON = dt.date(2026, 10, 26)

def test_menu_matches_readme_addendum31_and_34():
    assert len(L.MENU) == 10 and sum(l["stake"] for l in L.MENU) == 112500
    assert sum(l["stake"] for l in L.MENU if l["entry"] == "07:00") == 62700          # 月曜 07:00 の 23H × 3(DD40万換算)
    mon = sum(l["stake"] for l in L.MENU if 0 in l["wds"] and not l.get("gotobi")); assert mon == 72700 and mon * L.BOOST_MULT <= L.DAILY_STAKE_CAP
    nk = [l for l in L.MENU if l.get("gotobi")]
    assert [l["pair"] for l in nk] == ["USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY"] and all(l["kind"] == "15M" and l["sel"] == "LOW" and l["entry"] == "09:55" and l["judge"] == "10:05" and not l["next"] and l["stake"] == 7000 for l in nk)
    assert mon + sum(l["stake"] for l in nk) == 107700 <= L.DAILY_STAKE_CAP           # 月曜がゴトー日でも日次上限内(v1.8: 72,700 + 35,000)
    assert all(l["kind"] == "23H" and l["judge"] == "06:00" for l in L.MENU if not l.get("gotobi"))
    assert all((not l["next"]) == (l["entry"] < "06:00") for l in L.MENU if not l.get("gotobi"))      # 深夜建て(02:00)だけ同日判定
    assert all(l["stake"] <= L.MAX_STAKE for l in L.MENU) and len({l["id"] for l in L.MENU}) == 10

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
    fri = dt.date(2026, 10, 30); assert [l["id"] for l in L.MENU if L.is_due_today(l, fri)] == ["EURGBP_N6L", "AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK", "CHFJPY_NK", "CADJPY_NK"]   # 10/30 = 月末(ゴトー日)
    nov5 = dt.date(2026, 11, 5); assert [l["id"] for l in L.MENU if L.is_due_today(l, nov5)] == ["AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK", "CHFJPY_NK", "CADJPY_NK"]
    nov10 = dt.date(2026, 11, 10); assert [l["id"] for l in L.MENU if L.is_due_today(l, nov10)] == ["EURGBP_N6L", "AUDJPY_02", "USDJPY_NK", "EURJPY_NK", "GBPJPY_NK", "CHFJPY_NK", "CADJPY_NK"]
    jun_mon = dt.date(2026, 6, 1); assert "EURGBP_N6L" not in [l["id"] for l in L.MENU if L.is_due_today(l, jun_mon)]

def test_slot_selection_around_entry_time():
    now = dt.datetime(2026, 10, 26, 6, 58, tzinfo=L.JST)
    assert {l["entry"] for l in L.legs_for_slot(now)} == {"07:00"} and len(L.legs_for_slot(now)) == 3
    now = dt.datetime(2026, 10, 26, 9, 58, tzinfo=L.JST); assert L.legs_for_slot(now) == []           # v1.4: 月曜 10:00 以降の分割脚は無い(タスクは空振りで無害)
    now = dt.datetime(2026, 10, 26, 9, 54, tzinfo=L.JST); assert L.legs_for_slot(now) == []           # 10/26 はゴトー日でない → 09:54 起動は空振り
    now = dt.datetime(2026, 11, 5, 9, 54, tzinfo=L.JST); legs = L.legs_for_slot(now)                  # 11/5(木)ゴトー日 → 仲値 5 本(v1.8)
    assert [l["id"] for l in legs] == ["USDJPY_NK", "EURJPY_NK", "GBPJPY_NK", "CHFJPY_NK", "CADJPY_NK"] and all(l["_day"] == dt.date(2026, 11, 5) for l in legs)
    assert L.judge_utc(legs[0], legs[0]["_day"]) == dt.datetime(2026, 11, 5, 1, 5, tzinfo=L.UTC)   # v1.9: 09:50 枠(判定 10:05)
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
    frames = [upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85", status="Unknown"),
              upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85", status="Open"),
              upd("USDJPY|FE|15M|HIGHLOW|HIGH", "2026-11-05T01:05:00.000Z", "1.85", status="Unknown"),
              upd("USDJPY|FE|1H|HIGHLOW|LOW", "2026-11-05T02:00:00.000Z", "1.9"),
              upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85", status="Closed")]
    c = L.pick_contract(frames[:4], nk, day); assert c and c["name"] == "USDJPY|FE|15M|HIGHLOW|LOW" and c["expiration_time"] == "2026-11-05T01:05:00.000Z"
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
    async def fake_scan(wss, key, secs, done=None):
        scans.append(secs)
        frames = [upd("USDJPY|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85")]   # 1 つ前の枠だけ → まだ打ち切らない
        assert done is not None and not done(frames)
        frames += [upd(f"{p}|FE|15M|HIGHLOW|LOW", "2026-11-05T01:05:00.000Z", "1.85", status="Unknown") for p in ("USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY")]
        assert done(frames)   # 5 本そろった瞬間に打ち切る
        return frames
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        now = dt.datetime(2026, 11, 5, 9, 54, tzinfo=L.JST)
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), now) == 0
        e = dt.datetime(2026, 11, 5, 9, 55, tzinfo=L.JST)
        assert sleeps == [e - dt.timedelta(seconds=25), e + dt.timedelta(seconds=1)] and scans == [45]   # −25 秒から最長 +20 秒まで購読 → 定刻 +1 秒に発注
        buys = [c for c in calls if c[0] == "/trading/buy"]; assert len(buys) == 6 and all(c[2] == 8 for c in buys)   # 拒否 1 回 + 成功 5 本
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 6 and all(",7000,7,153.21," in r for r in rows[1:]) and rows[-1].startswith("2026-11-05,USDJPY_NK,USDJPY,LOW,1.85,7000")   # v1.16: 拒否された USDJPY は 2 巡目で約定するので行は最後
        assert [c[1]["contract"][:6] for c in buys] == ["USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY", "USDJPY"]   # 1 巡目で全脚 → 拒否された脚だけ再試行

def test_v116_fast_path_tries_every_leg_before_retrying(monkeypatch):
    """v1.16(追補77): 11/20 09:55 の実測。5 本とも 1 回目が 213、USDJPY・CADJPY は 3 回とも 213。前の脚の再試行が後ろの脚を待たせないこと、1 脚 3 回までで打ち切ること、送信間隔が FAST_GAP であること。"""
    clock = {"t": 1000.0}; sends = []
    monkeypatch.setattr(L.time, "time", lambda: clock["t"]); monkeypatch.setattr(L.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(L, "sleep_until", lambda t: None)
    n = {}
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 300000}}
        if path == "/trading/buy":
            p = body["contract"][:6]; n[p] = n.get(p, 0) + 1; sends.append((p, clock["t"])); clock["t"] += 0.9   # 応答まで 0.9 秒
            ok = {"EURJPY": 3, "GBPJPY": 2, "CHFJPY": 2}.get(p)
            if ok and n[p] >= ok: return 200, {"status": "success", "data": {"trade": 5, "order_properties": {"strike": 1.5}}}
            return 200, {"status": "fail", "data": None, "errors": [{"errorCode": 213, "description": "The rate has significantly shifted since you invested. Please try again."}]}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|15M|HIGHLOW|LOW", "2026-11-20T01:05:00.000Z", "1.85", status="Unknown") for p in ("USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 11, 20, 9, 54, tzinfo=L.JST)) == 0
        order = [p for p, _ in sends]
        assert order[:5] == ["USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY"]                       # 1 巡目: 全脚を 1 回ずつ
        assert order[5:10] == ["USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY"]                     # 2 巡目: 拒否された脚(今回は全部)
        assert order[10:] == ["USDJPY", "EURJPY", "CADJPY"] and n == {"USDJPY": 3, "EURJPY": 3, "GBPJPY": 2, "CHFJPY": 2, "CADJPY": 3}   # 3 巡目で打ち切り
        gaps = [round(b[1] - a[1], 3) for a, b in zip(sends, sends[1:])]
        assert all(abs(g - L.FAST_GAP) < 1e-6 for g in gaps)                                         # 送信間隔は 1.2 秒(応答待ち込み)
        assert sends[4][1] - sends[0][1] < 5.0                                                       # 5 本目の 1 回目は 1 本目の 4.8 秒後(11/20 は 20 秒後)
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 6 and sum(",7000,5,1.5," in r for r in rows) == 3 and sum("buy 拒否 [213]" in r for r in rows) == 2
        state = json.load(open(os.path.join(tmp, "_diag", "live_state.json"), encoding="utf-8"))["2026-11-20"]
        assert {k for k, v in state.items() if v["stake"] == 7000} == {"EURJPY_NK", "GBPJPY_NK", "CHFJPY_NK"} and len(state) == 5

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
    async def fake_scan(wss, key, secs, done=None): return frames
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

def test_run_entries_retries_transient_216_until_feed_is_live(monkeypatch):
    """v1.5a: 11/2(月)07:00 の実測。業者のレート配信が凍結している間は buy が 216 で拒否される → 15 秒おきに再試行し、配信開始後に約定する。"""
    calls = []; slept = []
    fake_now = {"t": dt.datetime(2026, 11, 9, 7, 0, 10, tzinfo=L.JST)}
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None): return fake_now["t"]
    monkeypatch.setattr(L.dt, "datetime", FakeDT)
    def fake_sleep(s): slept.append(s); fake_now["t"] = fake_now["t"] + dt.timedelta(seconds=s)
    monkeypatch.setattr(L.time, "sleep", fake_sleep); monkeypatch.setattr(L, "sleep_until", lambda t: None)
    def fake_rest(base, path, key, body=None, timeout=15):
        calls.append((path, body, timeout, fake_now["t"]))
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 1005350}}
        if path == "/trading/buy":
            if fake_now["t"] < dt.datetime(2026, 11, 9, 7, 8, 30, tzinfo=L.JST):   # 07:08:30 までレート凍結
                return 200, {"status": "fail", "data": None, "errors": [{"description": "Unable to process your request. Please try again later.", "errorCode": 216}]}
            return 200, {"status": "success", "data": {"trade": 9, "order_properties": {"strike": 175.9}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|23H|HIGHLOW|HIGH", "2026-11-09T21:00:00.000Z", "1.95", status="Open") for p in ("EURJPY", "AUDJPY", "NZDJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), fake_now["t"]) == 0
        buys = [c for c in calls if c[0] == "/trading/buy"]
        first_ok = next(c for c in buys if c[3] >= dt.datetime(2026, 11, 9, 7, 8, 30, tzinfo=L.JST))
        assert first_ok[3] < dt.datetime(2026, 11, 9, 7, 9, 0, tzinfo=L.JST)          # 配信開始から 15 秒以内に約定
        assert all(s in (L.FAST_GAP, 2, L.STALE_RETRY_SECS) or 4.0 <= s <= 8.0 for s in slept)   # 2 秒 → 保留(1.2 秒おきに次の脚)→ 15 秒おきの巡回、約定後の脚間は 4〜8 秒
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 4 and all(",9,175.9," in r for r in rows[1:])            # 3 本とも約定として記録

def test_run_entries_gives_up_at_deadline(monkeypatch):
    fake_now = {"t": dt.datetime(2026, 11, 9, 7, 0, 10, tzinfo=L.JST)}
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None): return fake_now["t"]
    monkeypatch.setattr(L.dt, "datetime", FakeDT)
    monkeypatch.setattr(L.time, "sleep", lambda s: fake_now.__setitem__("t", fake_now["t"] + dt.timedelta(seconds=s))); monkeypatch.setattr(L, "sleep_until", lambda t: None)
    n = {"buy": 0}
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 1005350}}
        if path == "/trading/buy": n["buy"] += 1; return 200, {"status": "fail", "errors": [{"errorCode": 216}]}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None): return [upd("EURJPY|FE|23H|HIGHLOW|HIGH", "2026-11-09T21:00:00.000Z", "1.95", status="Open")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), fake_now["t"])
        assert fake_now["t"] <= dt.datetime(2026, 11, 9, 7, 20, 30, tzinfo=L.JST) and n["buy"] >= 70   # 07:20 で打ち切り(約 80 回)
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        row = next(r for r in rows if ",EURJPY_N6," in r)
        assert "buy 拒否 [216]" in row and ",0,,," in row

def test_v114_frozen_leg_does_not_block_other_legs(monkeypatch):
    """v1.14(追補72): 11/16(月)の実測。EURJPY が 216 で 10 分凍結している間、AUDJPY・NZDJPY は試行されなかった → 凍結中の脚は保留に回し、配信が戻った脚から建てる。"""
    fake_now = {"t": dt.datetime(2026, 11, 16, 7, 0, 10, tzinfo=L.JST)}
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None): return fake_now["t"]
    monkeypatch.setattr(L.dt, "datetime", FakeDT)
    monkeypatch.setattr(L.time, "sleep", lambda s: fake_now.__setitem__("t", fake_now["t"] + dt.timedelta(seconds=s))); monkeypatch.setattr(L, "sleep_until", lambda t: None)
    T = lambda h, m, s=0: dt.datetime(2026, 11, 16, h, m, s, tzinfo=L.JST)
    thaw = {"EURJPY": T(7, 30), "AUDJPY": T(7, 3), "NZDJPY": T(7, 0)}   # EURJPY は打ち切り(07:20)まで凍結、AUDJPY は 07:03 まで、NZDJPY は最初から配信あり
    fills = {}; tries = {"EURJPY": 0, "AUDJPY": 0, "NZDJPY": 0}
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 400000}}
        if path == "/trading/buy":
            p = body["contract"][:6]; tries[p] += 1
            if fake_now["t"] < thaw[p]: return 200, {"status": "fail", "errors": [{"errorCode": 216}]}
            assert p not in fills; fills[p] = fake_now["t"]
            return 200, {"status": "success", "data": {"trade": 7, "order_properties": {"strike": 1.0}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|23H|HIGHLOW|HIGH", "2026-11-16T21:00:00.000Z", "1.95", status="Open") for p in ("EURJPY", "AUDJPY", "NZDJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), fake_now["t"]) == 0
        assert fills["NZDJPY"] < T(7, 0, 30)                          # 凍結していない脚は待たされない
        assert T(7, 3) <= fills["AUDJPY"] < T(7, 3, 25)               # 配信が戻ってから一巡以内
        assert "EURJPY" not in fills and fake_now["t"] <= T(7, 20, 30) and tries["EURJPY"] >= 60   # 凍結したままの脚だけ 07:20 で見送り
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert len(rows) == 4 and sum(",7,1.0," in r for r in rows) == 2 and sum("buy 拒否 [216]" in r for r in rows) == 1
        state = json.load(open(os.path.join(tmp, "_diag", "live_state.json"), encoding="utf-8"))["2026-11-16"]
        assert state["AUDJPY_N6"]["stake"] == 22700 and state["NZDJPY_N6"]["stake"] == 18700 and state["EURJPY_N6"]["stake"] == 0
        # 再実行しても二重発注しない
        n0 = sum(tries.values()); L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), T(7, 0, 10)); assert sum(tries.values()) == n0

def test_v115_monday_legs_skip_jp_holiday(monkeypatch):
    """v1.15(追補74): 日本の祝日(振替休日・年末年始を含む)の月曜は月曜 3 本を見送る。他の脚と通常の月曜は不変。"""
    mon = [l for l in L.MENU if l["id"].endswith("_N6")]; assert len(mon) == 3 and all(l.get("skip_jp_holiday") for l in mon)
    assert [l["id"] for l in L.MENU if l.get("skip_jp_holiday")] == ["EURJPY_N6", "AUDJPY_N6", "NZDJPY_N6"]
    D = dt.date
    for hol in (D(2026, 11, 23), D(2027, 1, 11), D(2027, 3, 22), D(2026, 5, 4), D(2029, 12, 31)):   # 勤労感謝の日・成人の日・振替休日・みどりの日・年末
        assert hol.weekday() == 0 and not any(L.is_due_today(l, hol) for l in mon), hol
    for normal in (D(2026, 11, 16), D(2026, 11, 30), D(2026, 12, 7)):
        assert all(L.is_due_today(l, normal) for l in mon), normal
    eg = next(l for l in L.MENU if l["id"] == "EURGBP_N6L"); assert L.is_due_today(eg, D(2026, 11, 23))            # 23:00 EURGBP は祝日でも建てる
    assert L.legs_for_slot(dt.datetime(2026, 11, 23, 6, 58, tzinfo=L.JST)) == []
    assert [l["id"] for l in L.legs_for_slot(dt.datetime(2026, 11, 23, 22, 58, tzinfo=L.JST))] == ["EURGBP_N6L"]
    assert len(L.legs_for_slot(dt.datetime(2026, 11, 30, 6, 58, tzinfo=L.JST))) == 3
    # 祝日の 06:58 起動: 発注も残高照会もせず、見送りを記録して終了
    calls = []
    monkeypatch.setattr(L, "rest", lambda *a, **k: calls.append(a) or (200, {}))
    with tempfile.TemporaryDirectory() as tmp:
        lp = os.path.join(tmp, "l.jsonl")
        assert L.run_entries("real", REAL, tmp, L.Log(lp), dt.datetime(2026, 11, 23, 6, 58, tzinfo=L.JST), only_ids=set()) == 0 and calls == []
        txt = open(lp, encoding="utf-8").read(); assert '"skip"' in txt and "EURJPY_N6" in txt and "2026-11-23" in txt
        assert not os.path.exists(os.path.join(tmp, "live_entries_real.csv"))

def test_v16_per_leg_account_routing(monkeypatch):
    """v1.6(追補37・裁定 B): live_real でも demo_legs(既定: 月曜 3 本 + 仲値 3 本)はお試し口座、EURGBP 23:00 と AUDJPY 02:00 は実口座。"""
    monkeypatch.setenv("THEOPTION_API_KEY", DEMO); monkeypatch.setenv("THEOPTION_API_KEY_REAL", REAL)
    monkeypatch.setattr(L, "HERE", tempfile.mkdtemp()); monkeypatch.setattr(L, "keep_awake", lambda: None)
    with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x", "live_real": True}, f)
    runs = []
    monkeypatch.setattr(L, "run_entries", lambda acc, key, out, log, now, only_ids=None: runs.append((acc, key, tuple(sorted(only_ids)))) or 0)
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None): return FakeDT.t
    monkeypatch.setattr(L.dt, "datetime", FakeDT)
    with tempfile.TemporaryDirectory() as tmp:
        FakeDT.t = dt.datetime(2026, 11, 3, 22, 58, tzinfo=L.JST)     # 火曜 22:58 → 23:00 EURGBP(11 月は対象月)は実口座
        assert L.main(["--out", tmp]) == 0 and runs == [("real", REAL, ("EURGBP_N6L",))]
        runs.clear(); FakeDT.t = dt.datetime(2026, 11, 4, 1, 58, tzinfo=L.JST)   # 水曜 01:58 → 02:00 AUDJPY プール脚は実口座
        assert L.main(["--out", tmp]) == 0 and runs == [("real", REAL, ("AUDJPY_02",))]
        runs.clear(); FakeDT.t = dt.datetime(2026, 11, 9, 6, 58, tzinfo=L.JST)   # 月曜 06:58 → v1.10: 3 本は実口座
        assert L.main(["--out", tmp]) == 0 and runs == [("real", REAL, ("AUDJPY_N6", "EURJPY_N6", "NZDJPY_N6"))]
        runs.clear(); FakeDT.t = dt.datetime(2026, 11, 5, 9, 54, tzinfo=L.JST)   # ゴトー日 09:54 → v1.13: 仲値 5 本も実口座
        assert L.main(["--out", tmp]) == 0 and runs == [("real", REAL, ("CADJPY_NK", "CHFJPY_NK", "EURJPY_NK", "GBPJPY_NK", "USDJPY_NK"))]
        # demo_legs に書いた脚だけお試しに戻せる
        with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x", "live_real": True, "demo_legs": ["EURJPY_N6", "AUDJPY_N6", "NZDJPY_N6"]}, f)
        runs.clear(); FakeDT.t = dt.datetime(2026, 11, 9, 6, 58, tzinfo=L.JST)
        assert L.main(["--out", tmp]) == 0 and runs == [("demo", DEMO, ("AUDJPY_N6", "EURJPY_N6", "NZDJPY_N6"))]
        # live_real が無ければ従来どおり全脚お試し(実口座キーがあっても)
        with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x"}, f)
        runs.clear(); FakeDT.t = dt.datetime(2026, 11, 3, 22, 58, tzinfo=L.JST)
        assert L.main(["--out", tmp]) == 0 and runs == [("demo", DEMO, ("EURGBP_N6L",))]
        # 実口座キーの iss が合わなければその口座は止まる(お試し側は影響なし)
        with open(os.path.join(L.HERE, "to_config.json"), "w", encoding="utf-8-sig") as f: json.dump({"out": "x", "live_real": True}, f)
        monkeypatch.setenv("THEOPTION_API_KEY_REAL", DEMO); runs.clear()
        assert L.main(["--out", tmp]) == 3 and runs == []
        monkeypatch.setenv("THEOPTION_API_KEY_REAL", REAL)
        # --settle は実口座・お試しの両方
        settles = []; monkeypatch.setattr(L, "run_settle", lambda acc, key, out, log: settles.append(acc) or 0)
        assert L.main(["--settle", "--out", tmp]) == 0 and settles == ["real", "demo"]

def test_v17_gotobi_kind_and_stake():
    """v1.7(追補43): 仲値脚は 25 日 ×1.5 / 月末 ×0.75 / 他 ×1.0。前倒し後の日付から名目ゴトー日を判定する。"""
    K = L.gotobi_kind
    assert K(dt.date(2026, 11, 5)) == "other" and K(dt.date(2026, 11, 13)) == "other"   # 11/15 日曜 → 11/13 金曜
    assert K(dt.date(2026, 11, 25)) == "25" and K(dt.date(2026, 10, 23)) == "25"        # 10/25 日曜 → 10/23 金曜
    assert K(dt.date(2026, 11, 30)) == "eom" and K(dt.date(2026, 1, 30)) == "eom"        # 1/31 土曜 → 1/30 金曜
    assert K(dt.date(2026, 12, 30)) == "eom" and K(dt.date(2026, 5, 1)) == "other"       # 大晦日前倒し / 5/5 → 5/1
    assert K(dt.date(2026, 11, 4)) is None and K(dt.date(2026, 11, 7)) is None
    nk = next(l for l in L.MENU if l["id"] == "USDJPY_NK"); mon = next(l for l in L.MENU if l["id"] == "EURJPY_N6")
    assert L.stake_for(nk, "1.85", dt.date(2026, 11, 25)) == 10500 and L.stake_for(nk, "1.85", dt.date(2026, 11, 30)) == 5200
    assert L.stake_for(nk, "1.85", dt.date(2026, 11, 5)) == 7000 and L.stake_for(nk, "1.85") == 7000      # day 無しは従来どおり
    assert L.stake_for(nk, "2.0", dt.date(2026, 11, 25)) == 15800                                         # BOOST ×1.5 と重なれば 7000×1.5×1.5=15,750 → 100 円丸め
    assert L.stake_for(mon, "1.95", dt.date(2026, 11, 30)) == 21300                                       # 23H 脚は影響なし
    assert 72700 + 5 * 10500 <= L.DAILY_STAKE_CAP and 72700 * L.BOOST_MULT + 5 * 10500 <= L.DAILY_STAKE_CAP   # 25 日が月曜でも日次上限内(v1.8)


def test_skew_gate_record_only(monkeypatch):
    """v1.11: SKEW 門は記録のみ。分位は直前 251 営業日のうち当日値より小さい割合、門 = 0.8 超。月曜 3 本にだけ記録し、失敗しても発注は変えない。"""
    d0 = dt.date(2025, 1, 1); days = []; d = d0
    while len(days) < 300:
        if d.weekday() < 5: days.append(d)
        d += dt.timedelta(days=1)
    fri = [x for x in days if x.weekday() == 4][-1]; mon = fri + dt.timedelta(days=3)
    def csv_for(v_fri): return "DATE,SKEW\n" + "\n".join(f"{x:%m/%d/%Y},{(v_fri if x == fri else 100 + (i % 100)):.2f}" for i, x in enumerate(days))
    st = L.skew_gate_state(csv_for(250.0), mon); assert st["ref_date"] == str(fri) and st["pct"] == 1.0 and st["on"] is True and st["stale_days"] == 0
    st = L.skew_gate_state(csv_for(50.0), mon); assert st["pct"] == 0.0 and st["on"] is False
    st = L.skew_gate_state(csv_for(179.5), mon); assert 0.7 < st["pct"] <= 0.8 and st["on"] is False     # 80 分位「超」だけ ON
    with pytest.raises(ValueError): L.skew_gate_state("DATE,SKEW\n01/02/2025,120\n", mon)
    legs_mon = [l for l in L.MENU if l["id"] in L.SKEW_LEGS]; legs_other = [l for l in L.MENU if l["id"] == "EURGBP_N6L"]
    with tempfile.TemporaryDirectory() as tmp:
        log = L.Log(os.path.join(tmp, "l.jsonl"))
        assert L.record_skew_gate(mon, legs_other, tmp, log) is None and not os.path.exists(os.path.join(tmp, "skew_gate_log.csv"))
        st = L.record_skew_gate(mon, legs_mon, tmp, log); assert "error" in st                                  # 取得失敗でも例外にしない
        monkeypatch.setattr(L, "fetch_skew_csv", lambda timeout=12: csv_for(250.0))
        st = L.record_skew_gate(mon, legs_mon, tmp, log); assert st["on"] is True
        rows = open(os.path.join(tmp, "skew_gate_log.csv"), encoding="utf-8").read().splitlines()
        assert rows[0] == "date,ref_date,skew,pct,on,error" and len(rows) == 3 and rows[2].startswith(f"{mon},{fri},250.0,1.0,True,")


def test_runup_record_only(monkeypatch):
    """v1.12: 仲値 run-up は記録のみ。09:30 と発注直前のレート差(pip)と上げ/下げを残し、余裕が無ければ飛ばす。ゴトー日以外は 09:30 の記録もしない。"""
    r0 = {"USDJPY": {"rate": 158.00}, "EURJPY": {"rate": 177.50}, "CADJPY": {"rate": 112.00}}
    r1 = {"USDJPY": {"rate": 158.05}, "EURJPY": {"rate": 177.44}, "GBPJPY": {"rate": 212.0}, "CADJPY": {"rate": 112.00}}
    assert L.runup_rows(r0, r1) == [("USDJPY", 158.0, 158.05, 5.0, True), ("EURJPY", 177.5, 177.44, -6.0, False), ("CADJPY", 112.0, 112.0, 0.0, False)]
    assert L.runup_rows(None, r1) == [] and L.runup_rows(r0, {"_error": "x"}) == []
    with tempfile.TemporaryDirectory() as tmp:
        log = L.Log(os.path.join(tmp, "l.jsonl")); slept = []
        monkeypatch.setattr(L, "sleep_until", lambda t: slept.append(t)); monkeypatch.setattr(L, "snap_rates_sync", lambda wss, key, pairs, secs: r0)
        assert L.run_ratesnap("demo", DEMO, tmp, log, dt.datetime(2026, 11, 19, 9, 29, tzinfo=L.JST)) == 0 and slept == []            # 11/19 はゴトー日でない
        assert L.run_ratesnap("demo", DEMO, tmp, log, dt.datetime(2026, 11, 20, 9, 29, tzinfo=L.JST)) == 0 and len(slept) == 1
        assert json.load(open(L.runup_path(tmp), encoding="utf-8"))["2026-11-20"]["USDJPY"]["rate"] == 158.0
        monkeypatch.setattr(L, "snap_rates_sync", lambda wss, key, pairs, secs: r1); day = dt.date(2026, 11, 20)
        assert L.record_runup("wss://x", DEMO, day, dt.datetime.now(L.JST) + dt.timedelta(seconds=2), tmp, log) is None                 # 残り 5 秒未満 → 飛ばす
        rows = L.record_runup("wss://x", DEMO, day, dt.datetime.now(L.JST) + dt.timedelta(seconds=30), tmp, log); assert len(rows) == 3
        lines = open(os.path.join(tmp, "nk_runup_log.csv"), encoding="utf-8").read().splitlines()
        assert lines[0] == "date,pair,rate_0930,rate_pre,pip,up" and lines[1] == "2026-11-20,USDJPY,158.0,158.05,5.0,True" and len(lines) == 4

def test_v117_friday_state_and_record_only(monkeypatch):
    """v1.17(追補96): 前の金曜の騰落は記録のみ。木 21:00 UTC → 金 21:00 UTC。金曜 21:00 の足が無い(夏時間の引け)ときは直前の足の終値。取得失敗は error を残して発注は続く。"""
    day = dt.date(2026, 11, 30)   # 月曜。金曜 = 11/27、木曜 = 11/26
    H = lambda d, h, o, c: (dt.datetime(2026, 11, d, h), o, c)
    bars = [H(26, 20, 174.00, 174.10), H(26, 21, 174.20, 174.25), H(27, 19, 173.90, 173.80), H(27, 20, 173.80, 173.50), H(27, 21, 173.40, 173.45)]
    st = L.friday_state(bars, day); assert st == {"thu": 174.2, "fri": 173.4, "ret_bp": -45.9, "down": True}
    st2 = L.friday_state(bars[:-1], day); assert st2["fri"] == 173.5 and st2["down"] is True                    # 金曜 21:00 の足なし → 20:00 の足の終値
    up = L.friday_state([H(26, 21, 174.0, 174.0), H(27, 21, 174.0, 174.0)], day); assert up["down"] is False and up["ret_bp"] == 0.0   # 変わらず = 下落ではない
    with pytest.raises(ValueError): L.friday_state([H(27, 21, 1.0, 1.0)], day)
    legs = [l for l in L.MENU if l["id"] in ("EURJPY_N6", "NZDJPY_N6", "EURGBP_N6L")]
    with tempfile.TemporaryDirectory() as tmp:
        log = L.Log(os.path.join(tmp, "l.jsonl"))
        out = L.record_friday(day, legs, tmp, log); assert set(out) == {"EURJPY_N6", "NZDJPY_N6"} and all("error" in v for v in out.values())   # 既定のテスト環境は offline
        monkeypatch.setattr(L, "fetch_hourly", lambda pair, timeout=12: bars)
        out = L.record_friday(day, legs, tmp, log); assert out["EURJPY_N6"]["down"] is True
        lines = open(os.path.join(tmp, "fri_down_log.csv"), encoding="utf-8").read().splitlines()
        assert lines[0] == "date,pair,thu,fri,ret_bp,down,error" and len(lines) == 5 and lines[3] == "2026-11-30,EURJPY,174.2,173.4,-45.9,True,"
        assert L.record_friday(day, [l for l in L.MENU if l.get("gotobi")], tmp, log) == {}                      # 月曜 3 本以外では何もしない

def _nk_run(monkeypatch, tmp, r0, r1):
    """11/20(ゴトー日・倍率 1.0)の 09:55 仲値を、09:30 のレート r0・発注直前のレート r1 で 1 回走らせ、通貨ごとの発注額を返す。"""
    clock = {"t": 1000.0}; bought = {}
    monkeypatch.setattr(L.time, "time", lambda: clock["t"]); monkeypatch.setattr(L.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(L, "sleep_until", lambda t: None)
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 300000}}
        if path == "/trading/buy": bought[body["contract"][:6]] = body["amount"]; return 200, {"status": "success", "data": {"trade": 5, "order_properties": {"strike": 1.5}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|15M|HIGHLOW|LOW", "2026-11-20T01:05:00.000Z", "1.85", status="Unknown") for p in ("USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    os.makedirs(os.path.join(tmp, "_diag"), exist_ok=True); json.dump({"2026-11-20": r0}, open(L.runup_path(tmp), "w", encoding="utf-8"))
    monkeypatch.setattr(L, "snap_rates_sync", lambda wss, key, pairs, secs: r1)
    monkeypatch.setattr(L, "record_runup", lambda wss, key, day, entry0, out_dir, log: L.runup_rows(r0, r1))     # 残り時間の判定はテスト対象外(test_runup_record_only で確認済み)
    assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 11, 20, 9, 54, tzinfo=L.JST)) == 0
    return bought

def test_v117_runup_sizing_off_keeps_stakes_and_logs_shadow(monkeypatch):
    """v1.17: RUNUP_SIZING は既定 OFF。発注額は変えず、ON だった場合の額(stake_if_sized)だけを記録する。"""
    monkeypatch.setattr(L, "RUNUP_SIZING", False)
    r0 = {"USDJPY": {"rate": 158.00}, "EURJPY": {"rate": 177.50}, "CADJPY": {"rate": 112.00}}
    r1 = {"USDJPY": {"rate": 158.05}, "EURJPY": {"rate": 177.44}, "CADJPY": {"rate": 112.00}, "GBPJPY": {"rate": 212.0}}
    with tempfile.TemporaryDirectory() as tmp:
        bought = _nk_run(monkeypatch, tmp, r0, r1)
        assert bought == {p: 7000 for p in ("USDJPY", "EURJPY", "GBPJPY", "CHFJPY", "CADJPY")}
        g = {j["frame"]["leg"]: j["frame"] for j in map(json.loads, open(os.path.join(tmp, "l.jsonl"), encoding="utf-8")) if j["kind"] == "gotobi"}
        assert g["USDJPY_NK"]["stake"] == 7000 and g["USDJPY_NK"]["stake_if_sized"] == 9800 and g["USDJPY_NK"]["runup_mult"] == 1.4
        assert g["EURJPY_NK"]["stake_if_sized"] == 2800 and g["CADJPY_NK"]["stake_if_sized"] == 2800               # 下げ・変わらずは ×0.4
        assert g["GBPJPY_NK"]["stake_if_sized"] == 7000 and g["CHFJPY_NK"]["runup_mult"] == 1.0                    # レートが片方でも無い通貨は ×1.0

def test_v117_runup_sizing_on_changes_stakes(monkeypatch):
    """v1.17: RUNUP_SIZING を ON にした場合(将来の版)。上げ ×1.4 / 他 ×0.4 / レート無し ×1.0。ゴトー日の倍率(25 日 ×1.5 など)の後に掛け、100 円単位。"""
    monkeypatch.setattr(L, "RUNUP_SIZING", True)
    assert L.runup_mult("USDJPY", [("USDJPY", 1, 2, 5.0, True)]) == 1.4 and L.runup_mult("USDJPY", [("USDJPY", 1, 1, 0.0, False)]) == 0.4 and L.runup_mult("USDJPY", None) == 1.0
    r0 = {"USDJPY": {"rate": 158.00}, "EURJPY": {"rate": 177.50}, "CADJPY": {"rate": 112.00}}
    r1 = {"USDJPY": {"rate": 158.05}, "EURJPY": {"rate": 177.44}, "CADJPY": {"rate": 112.00}}
    with tempfile.TemporaryDirectory() as tmp:
        bought = _nk_run(monkeypatch, tmp, r0, r1)
        assert bought == {"USDJPY": 9800, "EURJPY": 2800, "GBPJPY": 7000, "CHFJPY": 7000, "CADJPY": 2800}
        rows = open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()
        assert any(",USDJPY,LOW,1.85,9800," in r for r in rows) and any(",EURJPY,LOW,1.85,2800," in r for r in rows)

def test_v118_stake_scale_and_cap(monkeypatch):
    """v1.18(追補102): 発注額 = 基準額 × STAKE_SCALE(100 円単位)。1.49 で 50 万円版。1 日上限 240,000 に収まること。"""
    monkeypatch.setattr(L, "STAKE_SCALE", 1.49)
    by = {l["id"]: L.base_stake(l) for l in L.MENU + L.ME_LEGS}
    assert by["EURJPY_N6"] == 31700 and by["AUDJPY_N6"] == 33800 and by["NZDJPY_N6"] == 27900 and by["EURGBP_N6L"] == 14900 and by["AUDJPY_02"] == 7200
    assert by["USDJPY_NK"] == 10400 and by["EURUSD_ME"] == 14900
    nk = next(l for l in L.MENU if l["id"] == "USDJPY_NK"); mon = next(l for l in L.MENU if l["id"] == "EURJPY_N6")
    assert L.stake_for(nk, "1.85", dt.date(2026, 11, 25)) == 15600 and L.stake_for(nk, "1.85", dt.date(2026, 11, 30)) == 7800 and L.stake_for(mon, "1.95", dt.date(2026, 11, 30)) == 31700
    assert L.stake_for(mon, "1.89") == 0 and L.stake_for(mon, "2.0") == 47550
    monday = 31700 + 33800 + 27900
    assert monday + 5 * 15600 + 14900 <= L.DAILY_STAKE_CAP and monday + 5 * 7800 + 14900 + 3 * 14900 <= L.DAILY_STAKE_CAP

def test_v118_month_end_legs_calendar():
    """v1.18: 月末脚の日付。ロンドンの最終営業日(土日は前倒し)。夏時間は同日 23:00 JST、冬時間は翌日 00:00 JST。それ以外の日は無い。"""
    w = L.month_end_legs(dt.date(2026, 12, 1)); assert [l["id"] for l in w] == ["EURUSD_ME", "GBPUSD_ME", "AUDUSD_ME"] and w[0]["entry"] == "00:00" and w[0]["judge"] == "01:00" and w[0]["_ldn"] == dt.date(2026, 11, 30)
    assert L.judge_utc(w[0], dt.date(2026, 12, 1)) == dt.datetime(2026, 11, 30, 16, 0, tzinfo=L.UTC)             # ロンドン 16:00(冬)
    assert L.month_end_legs(dt.date(2026, 11, 30)) == [] and L.month_end_legs(dt.date(2026, 12, 2)) == []
    s = L.month_end_legs(dt.date(2026, 7, 31)); assert s[0]["entry"] == "23:00" and s[0]["next"] is True and L.judge_utc(s[0], dt.date(2026, 7, 31)) == dt.datetime(2026, 7, 31, 15, 0, tzinfo=L.UTC)   # ロンドン 16:00(夏)
    assert L.month_end_legs(dt.date(2026, 8, 1)) == []
    o = L.month_end_legs(dt.date(2026, 10, 31)); assert o and o[0]["_ldn"] == dt.date(2026, 10, 30) and o[0]["entry"] == "00:00"   # 10/31 は土曜 → 10/30(金)。夏時間は 10/25 に終了済み
    assert L.month_end_legs(dt.date(2026, 10, 30)) == []
    m = L.month_end_legs(dt.date(2026, 5, 29)); assert m and m[0]["entry"] == "23:00"                              # 5/31 は日曜 → 5/29(金)
    assert L.london_bst(dt.date(2026, 3, 29)) and not L.london_bst(dt.date(2026, 3, 27)) and not L.london_bst(dt.date(2026, 10, 25))
    slot = L.legs_for_slot(dt.datetime(2026, 11, 30, 23, 58, tzinfo=L.JST)); assert sorted(l["id"] for l in slot) == ["AUDUSD_ME", "EURUSD_ME", "GBPUSD_ME"] and slot[0]["_day"] == dt.date(2026, 12, 1)
    slot = L.legs_for_slot(dt.datetime(2026, 7, 31, 22, 58, tzinfo=L.JST)); assert sorted(l["id"] for l in slot) == ["AUDUSD_ME", "EURGBP_N6L", "EURUSD_ME", "GBPUSD_ME"]

def test_v118_spx_state():
    """v1.18: S&P500 の月間騰落。当日(ロンドンの最終営業日)の足は使わず、前営業日の終値と前月末の終値を比べる。足りない・古いときは例外(= 見送り)。"""
    D = dt.date; bars = [(D(2026, 10, 29), 5000.0), (D(2026, 10, 30), 5010.0), (D(2026, 11, 2), 5050.0), (D(2026, 11, 27), 5100.0), (D(2026, 11, 30), 4000.0)]
    st = L.spx_mtd_state(bars, D(2026, 11, 30)); assert st == {"ref": "2026-11-27", "base": "2026-10-30", "mtd_pct": 1.8, "up": True}
    assert L.spx_mtd_state([(D(2026, 10, 30), 5010.0), (D(2026, 11, 27), 5010.0)], D(2026, 11, 30))["up"] is False       # 変わらず = 株高ではない
    with pytest.raises(ValueError): L.spx_mtd_state([(D(2026, 11, 27), 5100.0)], D(2026, 11, 30))                         # 前月の足が無い
    with pytest.raises(ValueError): L.spx_mtd_state([(D(2026, 10, 30), 5010.0), (D(2026, 11, 20), 5100.0)], D(2026, 11, 30))   # 直近の足が 6 日以上前

def _me_run(monkeypatch, tmp, spx):
    monkeypatch.setattr(L, "STAKE_SCALE", 1.49); monkeypatch.setattr(L, "sleep_until", lambda t: None); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    bought = []
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 450000}}
        if path == "/trading/buy": bought.append((body["contract"], body["amount"])); return 200, {"status": "success", "data": {"trade": 9, "order_properties": {"strike": 1.1}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|1H|HIGHLOW|{sel}", "2026-11-30T16:00:00.000Z", "1.90") for p in ("EURUSD", "GBPUSD", "AUDUSD") for sel in ("HIGH", "LOW")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    def gone(timeout=12): raise OSError("offline")
    monkeypatch.setattr(L, "fetch_spx_daily", (lambda timeout=12: spx) if spx is not None else gone)
    assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 11, 30, 23, 58, tzinfo=L.JST)) == 0
    return bought, open(os.path.join(tmp, "live_entries_demo.csv"), encoding="utf-8").read().splitlines()

def test_v118_month_end_buys_high_only_when_spx_up(monkeypatch):
    """v1.18: 月末脚。S&P500 が月間プラスなら 3 通貨を HIGH で 14,900 円ずつ。マイナスの月と取得失敗の月は発注せず、見送りを記録する(同じ日に再実行しても発注しない)。"""
    D = dt.date; up = [(D(2026, 10, 30), 5000.0), (D(2026, 11, 27), 5100.0)]; dn = [(D(2026, 10, 30), 5000.0), (D(2026, 11, 27), 4900.0)]
    with tempfile.TemporaryDirectory() as tmp:
        bought, rows = _me_run(monkeypatch, tmp, up)
        assert bought == [(f"{p}|FE|1H|HIGHLOW|HIGH", 14900) for p in ("EURUSD", "GBPUSD", "AUDUSD")]
        assert len(rows) == 4 and rows[1].startswith("2026-12-01,EURUSD_ME,EURUSD,HIGH,1.90,14900,9,1.1,EURUSD|FE|1H|HIGHLOW|HIGH")
    for spx, word in ((dn, "月間 -2.0%"), (None, "取得失敗")):
        with tempfile.TemporaryDirectory() as tmp:
            bought, rows = _me_run(monkeypatch, tmp, spx)
            assert bought == [] and len(rows) == 4 and all(",0,,,," in r and word in r for r in rows[1:])
            state = json.load(open(os.path.join(tmp, "_diag", "live_state.json"), encoding="utf-8"))["2026-12-01"]
            assert set(state) == {"EURUSD_ME", "GBPUSD_ME", "AUDUSD_ME"} and all(v["stake"] == 0 for v in state.values())
            assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 11, 30, 23, 59, tzinfo=L.JST)) == 0 and bought == []

def test_v119_sizing_is_on_and_scale(monkeypatch):
    """v1.19(追補104): 強弱は 2 つともオン、倍率 1.67、1 日上限 300,000。最大の日(金曜下落の月曜 + 25 日の仲値が全通貨上げ + EURGBP)が上限内。"""
    monkeypatch.setattr(L, "STAKE_SCALE", 1.67)
    assert L.RUNUP_SIZING is True and L.FRI_SIZING is True and L.DAILY_STAKE_CAP == 300000
    by = {l["id"]: L.base_stake(l) for l in L.MENU + L.ME_LEGS}
    assert (by["EURJPY_N6"], by["AUDJPY_N6"], by["NZDJPY_N6"], by["EURGBP_N6L"], by["AUDJPY_02"], by["USDJPY_NK"], by["EURUSD_ME"]) == (35600, 37900, 31200, 16700, 8000, 11700, 16700)
    mon = sum(round(by[k] * 1.25 / 100) * 100 for k in ("EURJPY_N6", "AUDJPY_N6", "NZDJPY_N6")); nk = round(round(11700 * 1.5 / 100) * 100 * 1.4 / 100) * 100
    assert mon == 130900 and nk == 24600 and mon + 5 * nk + by["EURGBP_N6L"] <= L.DAILY_STAKE_CAP
    assert L.fri_mult({"ret_bp": -45.9, "down": True}) == 1.25 and L.fri_mult({"ret_bp": 12.0, "down": False}) == 0.75 and L.fri_mult({"ret_bp": 0.0, "down": False}) == 0.75
    assert L.fri_mult({"error": "x"}) == 1.0 and L.fri_mult(None) == 1.0 and L.fri_mult({"ret_bp": -900.0, "down": True}) == 1.0     # 取得失敗・異常値は ×1.0
    assert L.runup_mult("USDJPY", [("USDJPY", 158.0, 160.0, 200.0, True)]) == 1.0                                                    # 150pip 超は読み取り異常 → ×1.0

def test_v119_monday_legs_sized_by_friday(monkeypatch):
    """v1.19: 月曜 3 本は前の金曜が下落なら ×1.25、上昇なら ×0.75、取得失敗なら ×1.0(100 円単位)。EURGBP など他の脚は変えない。"""
    monkeypatch.setattr(L, "STAKE_SCALE", 1.67); monkeypatch.setattr(L, "sleep_until", lambda t: None); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    H = lambda d, h, o, c: (dt.datetime(2026, 11, d, h), o, c)
    down = [H(26, 21, 174.20, 174.25), H(27, 21, 173.40, 173.45)]; up = [H(26, 21, 174.20, 174.25), H(27, 21, 174.90, 174.95)]
    def fetch(pair, timeout=12):
        if pair == "EURJPY": return down
        if pair == "AUDJPY": return up
        raise OSError("offline")
    monkeypatch.setattr(L, "fetch_hourly", fetch); bought = {}
    def fake_rest(base, path, key, body=None, timeout=15):
        if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 450000}}
        if path == "/trading/buy": bought[body["contract"][:6]] = body["amount"]; return 200, {"status": "success", "data": {"trade": 3, "order_properties": {"strike": 100.0}}}
        return 200, {"status": "success", "data": {"isActive": True}}
    monkeypatch.setattr(L, "rest", fake_rest)
    async def fake_scan(wss, key, secs, done=None):
        return [upd(f"{p}|FE|23H|HIGHLOW|HIGH", "2026-11-30T21:00:00.000Z") for p in ("EURJPY", "AUDJPY", "NZDJPY")]
    monkeypatch.setattr(L, "scan_contracts", fake_scan)
    with tempfile.TemporaryDirectory() as tmp:
        assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 11, 30, 6, 58, tzinfo=L.JST)) == 0
        assert bought == {"EURJPY": 44500, "AUDJPY": 28400, "NZDJPY": 31200}                                   # 35,600×1.25 / 37,900×0.75 / 31,200×1.0
        z = [json.loads(x)["frame"] for x in open(os.path.join(tmp, "l.jsonl"), encoding="utf-8") if json.loads(x)["kind"] == "fri_sizing"]
        assert [(f["leg"], f["mult"], f["stake"]) for f in z] == [("EURJPY_N6", 1.25, 44500), ("AUDJPY_N6", 0.75, 28400), ("NZDJPY_N6", 1.0, 31200)]

def test_v120_ny_state_and_mult():
    """v1.20(追補107〜109): AUDJPY 02:00 の強弱。建ての 4 時間前(13:00 UTC)の始値 → 建て時刻(17:00 UTC)の始値。17:00 の足がまだ無ければ直前の足の終値。"""
    H = lambda h, o, c: (dt.datetime(2026, 11, 30, h), o, c); e = dt.datetime(2026, 11, 30, 17, 0, 10)
    bars = [H(12, 105.90, 106.00), H(13, 106.00, 105.80), H(14, 105.80, 105.70), H(15, 105.70, 105.60), H(16, 105.60, 105.47), H(17, 105.47, 105.50)]
    assert L.ny_state(bars, e) == {"ref": 106.0, "now": 105.47, "ret_bp": -50.0, "down": True}
    assert L.ny_state(bars[:-1], e)["now"] == 105.47                                                       # 17:00 の足なし → 16:00 の足の終値
    assert L.ny_state([H(13, 106.0, 106.0), H(17, 106.0, 106.0)], e)["down"] is False                       # 変わらず = 下げではない
    with pytest.raises(ValueError): L.ny_state(bars[2:], e)                                                 # 13:00 の足が無い
    with pytest.raises(ValueError): L.ny_state(bars[:2], e)                                                 # 直前 2 時間の足が無い
    assert L.aj_mult({"ret_bp": -50.0, "down": True}) == 1.25 and L.aj_mult({"ret_bp": 10.0, "down": False}) == 0.75
    assert L.aj_mult({"error": "x"}) == 1.0 and L.aj_mult({"ret_bp": -400.0, "down": True}) == 1.0 and L.AJ_SIZING is True

def test_v120_audjpy02_sized_by_ny_session(monkeypatch):
    """v1.20: 02:00 の AUDJPY は、直前 4 時間に下げていれば ×1.25、そうでなければ ×0.75、取得失敗なら ×1.0。記録は aj_ny_log.csv。"""
    monkeypatch.setattr(L, "STAKE_SCALE", 1.67); monkeypatch.setattr(L, "sleep_until", lambda t: None); monkeypatch.setattr(L.time, "sleep", lambda s: None)
    H = lambda h, o, c: (dt.datetime(2026, 12, 1, h), o, c)   # 12/2(水)02:00 JST = 12/1 17:00 UTC
    def run(bars):
        bought = []
        def fake_rest(base, path, key, body=None, timeout=15):
            if path == "/wallet/balance": return 200, {"status": "success", "data": {"balance": 450000}}
            if path == "/trading/buy": bought.append(body["amount"]); return 200, {"status": "success", "data": {"trade": 4, "order_properties": {"strike": 105.5}}}
            return 200, {"status": "success", "data": {"isActive": True}}
        monkeypatch.setattr(L, "rest", fake_rest)
        async def fake_scan(wss, key, secs, done=None): return [upd("AUDJPY|FE|23H|HIGHLOW|HIGH", "2026-12-01T21:00:00.000Z")]
        monkeypatch.setattr(L, "scan_contracts", fake_scan)
        if bars is None:
            def gone(pair, timeout=12): raise OSError("offline")
            monkeypatch.setattr(L, "fetch_hourly", gone)
        else: monkeypatch.setattr(L, "fetch_hourly", lambda pair, timeout=12: bars)
        with tempfile.TemporaryDirectory() as tmp:
            assert L.run_entries("demo", DEMO, tmp, L.Log(os.path.join(tmp, "l.jsonl")), dt.datetime(2026, 12, 2, 1, 58, tzinfo=L.JST)) == 0
            return bought, open(os.path.join(tmp, "aj_ny_log.csv"), encoding="utf-8").read().splitlines()
    b, rows = run([H(13, 106.00, 105.9), H(16, 105.60, 105.47)]); assert b == [10000] and rows[1] == "2026-12-02,106.0,105.47,-50.0,True,1.25,"   # 8,000 × 1.25
    b, rows = run([H(13, 105.00, 105.1), H(17, 105.40, 105.4)]); assert b == [6000] and rows[1].endswith(",False,0.75,")                        # 8,000 × 0.75
    b, rows = run(None); assert b == [8000] and rows[1].endswith(",1.0,OSError('offline')")                                                     # 取得失敗 → 基準額
