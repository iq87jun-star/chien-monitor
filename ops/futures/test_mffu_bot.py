# -*- coding: utf-8 -*-
"""オフライン検証: python -m pytest ops/futures -q(ネットワーク・秘密なし)。"""
import datetime as dt, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mffu_bot as B

def test_third_friday():
    assert B.third_friday(2026, 12) == dt.date(2026, 12, 18) and B.third_friday(2026, 3) == dt.date(2026, 3, 20)

def test_front_contract_roll():
    assert B.front_contract("MES", dt.date(2026, 10, 12)) == "MESZ2026"
    assert B.front_contract("MES", dt.date(2026, 12, 7)) == "MESZ2026"      # 満期 12/18 の前々週月曜 → 当該限月
    assert B.front_contract("MES", dt.date(2026, 12, 14)) == "MESH2027"     # 満期週の月曜 → 次限月
    assert B.front_contract("MNQ", dt.date(2026, 12, 21)) == "MNQH2027"
    assert B.front_contract("MYM", dt.date(2027, 3, 8)) == "MYMH2027" and B.front_contract("MYM", dt.date(2027, 3, 15)) == "MYMM2027"

def _cfg(tmp):
    hol = os.path.join(tmp, "h.csv"); open(hol, "w").write("cal,date,name\nNYSE,2026-09-07,Labor Day\n")
    return dict(transport="dry", holidays_csv=hol, log_csv=os.path.join(tmp, "log.csv"), state_json=os.path.join(tmp, "state.json"), max_contracts_total=5, keepalive_wait_sec=0, send_signal_price=False)

def test_with_price_optional(monkeypatch=None):
    B.last_price = lambda root, timeout=6: 6000.25 if root == "MES" else None
    assert B.with_price({"action": "buy"}, "MES", {})["signalPrice"] == 6000.25
    assert "signalPrice" not in B.with_price({"action": "buy"}, "MNQ", {})          # 取れなければ省く
    assert "signalPrice" not in B.with_price({"action": "sell"}, "MES", {})         # 決済には付けない
    assert "signalPrice" not in B.with_price({"action": "buy"}, "MES", {"send_signal_price": False})

def test_plan_skips():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp)
        legs, why = B.plan(cfg, dt.date(2026, 10, 13)); assert "not_monday" in why
        legs, why = B.plan(cfg, dt.date(2026, 9, 7)); assert "holiday" in why
        legs, why = B.plan(cfg, dt.date(2026, 10, 12)); assert why == [] and sum(l["qty"] for l in legs) == 5 and [l["contract"] for l in legs] == ["MESZ2026", "MNQZ2026", "MYMZ2026"]
        cfg["max_contracts_total"] = 4; assert any(w.startswith("max_contracts_total") for w in B.plan(cfg, dt.date(2026, 10, 12))[1])

class Rec:
    name = "rec"
    def __init__(self): self.sent = []
    def send(self, p): self.sent.append(p); return "ok"

def test_entry_exit_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp); tr = Rec(); day = dt.date(2026, 10, 12)
        B.run(cfg, "exit", day, tr); assert tr.sent == []                       # 建てていなければ何も送らない
        B.run(cfg, "entry", day, tr); B.run(cfg, "entry", day, tr); assert len(tr.sent) == 3 and all(p["action"] == "buy" for p in tr.sent)
        B.run(cfg, "exit", day, tr); assert len(tr.sent) == 6 and all(p["sentiment"] == "flat" for p in tr.sent[3:])
        B.run(cfg, "check", day, tr); assert len(tr.sent) == 6                   # 決済済みなら再送しない
        rows = open(cfg["log_csv"]).read().splitlines(); assert len(rows) == 1 + 1 + 3 + 3   # ヘッダ + nothing_to_exit + 建て 3 + 決済 3
        st = json.load(open(cfg["state_json"])); assert st["2026-10-12"]["exited"] is True

def test_check_resends_when_not_exited():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp); tr = Rec(); day = dt.date(2026, 10, 12)
        B.run(cfg, "entry", day, tr); B.run(cfg, "check", day, tr); assert len(tr.sent) == 6 and tr.sent[-1]["extras"]["why"] == "check"

def test_keepalive_only_after_missed_monday():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp); tr = Rec()
        B.run(cfg, "keepalive", dt.date(2026, 9, 8), tr); assert len(tr.sent) == 2 and tr.sent[0]["quantity"] == 1 and tr.sent[1]["sentiment"] == "flat"   # 9/7 Labor Day の翌火曜
        B.run(cfg, "keepalive", dt.date(2026, 9, 8), tr); assert len(tr.sent) == 2                                   # 二重にしない
        B.run(cfg, "entry", dt.date(2026, 10, 12), tr); n = len(tr.sent); B.run(cfg, "keepalive", dt.date(2026, 10, 13), tr); assert len(tr.sent) == n   # 月曜に建てた週は不要
        B.run(cfg, "keepalive", dt.date(2026, 10, 14), tr); assert len(tr.sent) == n                                 # 水曜は何もしない
        B.run(cfg, "keepalive", dt.date(2026, 10, 15), tr); assert len(tr.sent) == n + 2                             # 木曜は毎週
        B.run(cfg, "keepalive", dt.date(2026, 10, 15), tr); assert len(tr.sent) == n + 2                             # 二重にしない
        B.run(cfg, "test", dt.date(2026, 10, 10), tr); assert len(tr.sent) == n + 4 and tr.sent[-2]["extras"]["why"] == "test"   # test は曜日不問
