# -*- coding: utf-8 -*-
"""
verify_profit_lock_logic.py — +7%利益ロック(docs/100 A-1)の状態機械をPythonで写像し、
合成equityパスで論理検証する(ユニットテスト)。

⚠ これは「ロジックの正しさ」の検証であり、性能(通過率・期待値)の主張ではない。
   ロックは月内解像度のMCでは表現できない(intraday equity依存)ため、性能面は
   docs/100 §1 の定性的整理+デモ前進検証で確認する(数字を盛らない規律)。

EA実装(Chien_Seasonal_Top_EA v1.10 / Chien_PortfolioD_Prop3 v1.10)と同じ意味論:
  - gain = (equity - initBal)/initBal * 100
  - gain >= LockClose(7.5) : 全決済 + 恒久ロック(PASS_LOCK, 以後新規なし)
  - gain >= LockArm(7.0)   : 新規停止(水準判定=gainが下回れば自動再開)
  - フロア/日次ガードはロックとは独立に先に評価される(EAの評価順も同じ:
    floor → PROFIT_LOCK → daily)
"""
import json, os

ARM = 7.0
CLOSE = 7.5


class ProfitLockEA:
    """EAのOnTimerガード評価順を写像した最小状態機械"""

    def __init__(self, init_bal=100000.0, arm=ARM, close=CLOSE,
                 floor_pct=8.0, daily_pct=4.0):
        self.init = init_bal
        self.arm = arm
        self.close = close
        self.floor_pct = floor_pct
        self.daily_pct = daily_pct
        self.lock_done = False
        self.halted = False
        self.day_halt = False
        self.day_start_eq = init_bal
        self.events = []

    def new_day(self, eq):
        self.day_start_eq = eq
        self.day_halt = False

    def on_timer(self, eq):
        """returns dict(can_open, closed_all_reason)"""
        closed = None
        # 1) フロア(恒久)
        if not self.halted and eq <= self.init * (1 - self.floor_pct / 100):
            self.halted = True
            closed = "FLOOR"
        if self.halted:
            return dict(can_open=False, closed=closed or "HALTED")
        # 2) 利益ロック
        gain = (eq - self.init) / self.init * 100
        if not self.lock_done and gain >= self.close:
            self.lock_done = True
            closed = "PROFIT_LOCK"
            self.events.append(("LOCK", round(gain, 3)))
        armed = (not self.lock_done) and gain >= self.arm
        if self.lock_done:
            return dict(can_open=False, closed=closed or "PROFIT_LOCK")
        # 3) 日次
        if not self.day_halt and eq <= self.day_start_eq * (1 - self.daily_pct / 100):
            self.day_halt = True
            closed = "DAILY_STOP"
        if self.day_halt:
            return dict(can_open=False, closed=closed)
        return dict(can_open=not armed, closed=None)


def run_path(path, **kw):
    ea = ProfitLockEA(**kw)
    log = []
    for step in path:
        if step == "NEWDAY":
            ea.new_day(log[-1]["eq"] if log else ea.init)
            continue
        r = ea.on_timer(step)
        log.append(dict(eq=step, **r))
    return ea, log


def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return bool(cond)


def main():
    ok = True
    B = 100000.0
    print("== T1: 通常上昇 → +7%で新規停止 → +7.5%で全決済ロック ==")
    ea, log = run_path([B * 1.02, B * 1.069, B * 1.071, B * 1.074, B * 1.076, B * 1.10])
    ok &= check("+6.9%までは新規可", log[1]["can_open"] is True)
    ok &= check("+7.1%で新規停止(建玉は維持)", log[2]["can_open"] is False and log[2]["closed"] is None)
    ok &= check("+7.6%で全決済(PROFIT_LOCK)", log[4]["closed"] == "PROFIT_LOCK")
    ok &= check("ロック後は恒久停止", log[5]["can_open"] is False and ea.lock_done)

    print("== T2: +7%到達後に後退 → 新規が自動再開(水準判定) ==")
    ea, log = run_path([B * 1.071, B * 1.065, B * 1.072])
    ok &= check("+7.1%で停止", log[0]["can_open"] is False)
    ok &= check("+6.5%へ後退で再開", log[1]["can_open"] is True)
    ok &= check("再度+7.2%で停止(ロックは未発火)", log[2]["can_open"] is False and not ea.lock_done)

    print("== T3: ギャップで7.5%を飛び越えてもロック発火 ==")
    ea, log = run_path([B * 1.03, B * 1.09])
    ok &= check("+9%到達の足で即全決済", log[1]["closed"] == "PROFIT_LOCK")
    ok &= check("実現gainは到達時点の値(=7.5%ではなく9%)", ea.events[0][1] >= 8.9)

    print("== T4: フロアはロックより優先(評価順) ==")
    ea, log = run_path([B * 0.915])
    ok &= check("-8.5%でフロア発動・恒久停止", log[0]["closed"] == "FLOOR" and ea.halted)

    print("== T5: 日次ガードとロックの独立性 ==")
    ea = ProfitLockEA()
    ea.new_day(B * 1.072)                      # +7.2%で日をまたぐ
    r1 = ea.on_timer(B * 1.072)
    r2 = ea.on_timer(B * 1.028)                # 当日-4.1%(だが総gain+2.8%)
    ok &= check("armed中でも日次-4%で当日停止", r1["can_open"] is False and r2["closed"] == "DAILY_STOP")

    print("== T6: ロック無効化(閾値をフェーズ目標超に設定)の等価性 ==")
    ea, log = run_path([B * 1.079], arm=99.0, close=99.9)
    ok &= check("arm/closeを高くすればロックは事実上無効", log[0]["can_open"] is True)

    out = dict(all_pass=bool(ok), arm=ARM, close=CLOSE,
               note="logic verification only; no performance claim")
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"), exist_ok=True)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "verify_profit_lock.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(("ALL PASS" if ok else "FAILURES PRESENT"), "->", path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
