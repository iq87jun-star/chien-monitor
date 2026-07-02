# -*- coding: utf-8 -*-
"""
verify_risk_guard.py — Max Risk 3%ガード(docs/100 §2)の
(a) 集計ロジックのPython写像テスト と (b) 既定サイズでの解析的影響評価。

⚠ (b)は新規バックテストではない。EAの既定input(検証済みサイズ)から
   「SL到達時の想定損失」を代数的に導くだけ(数字を盛らない規律)。
   結論: E5の1レッグ=カタストロフィSL(2.5×ATRmn)で3.90% > 3.0% ゆえ、
   ENFORCE既定にすると検証済み挙動から大幅乖離する → 既定はMONITOR。
"""
import json, os

# --- Chien_PortfolioD_Prop3 v1.1x の既定input(docs/76 median-3標準) ---
PD = dict(
    v7_weekly=1.95, v7_shots=12,          # SL=2.5×ATR(H1)でサイズ済 → SL到達損=perShot
    emon_weekly=1.95, emon_shots=6,
    v4_per_trade=0.58, v4_max_concurrent=9,
    e5_leg_sigma=1.56, e5_cat_atr=2.5, e5_legs=4,  # legRisk=1×ATRmn相当 → SL到達損=2.5×legRisk
)


def sleeve_sl_risks():
    r = {}
    r["v7_per_shot"] = PD["v7_weekly"] / PD["v7_shots"]
    r["v7_full_week"] = PD["v7_weekly"]
    r["emon_per_shot"] = PD["emon_weekly"] / PD["emon_shots"]
    r["emon_full_week"] = PD["emon_weekly"]
    r["v4_per_trade"] = PD["v4_per_trade"]
    r["v4_all9"] = PD["v4_per_trade"] * PD["v4_max_concurrent"]
    r["e5_per_leg"] = PD["e5_leg_sigma"] * PD["e5_cat_atr"]
    r["e5_all4"] = r["e5_per_leg"] * PD["e5_legs"]
    return {k: round(v, 3) for k, v in r.items()}


# --- ガード集計ロジックの写像(EAのOpenRiskPct/RiskGuardBlockedと同じ意味論) ---
def open_risk_pct(positions, init_bal, no_sl_assume=10.0):
    total = 0.0
    for p in positions:
        if p.get("sl_risk_money") is not None:      # SLあり: |open-SL|換算の損失額
            total += p["sl_risk_money"]
        else:                                        # SLなし: 建玉額×assume%
            total += p["notional"] * no_sl_assume / 100.0
    return 100.0 * total / init_bal


def blocked(positions, init_bal, mode="MONITOR", cap=3.0):
    if mode == "OFF" or cap <= 0:
        return False
    r = open_risk_pct(positions, init_bal)
    if r <= cap:
        return False
    return mode == "ENFORCE"


def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return bool(cond)


def main():
    ok = True
    B = 100000.0
    print("== (a) 集計ロジック写像テスト ==")
    pos_v7 = [dict(sl_risk_money=B * 0.001625)] * 12          # v7フル12ショット
    ok &= check("v7フル週=1.95% → 3%以下で非ブロック",
                abs(open_risk_pct(pos_v7, B) - 1.95) < 1e-9 and not blocked(pos_v7, B, "ENFORCE"))
    pos_e5 = [dict(sl_risk_money=B * 0.039)]                  # E5 1レッグ(2.5×1.56%)
    ok &= check("E5 1レッグ=3.90% → ENFORCEでブロック", blocked(pos_e5, B, "ENFORCE"))
    ok &= check("同状態でもMONITORは非ブロック(記録のみ)", not blocked(pos_e5, B, "MONITOR"))
    pos_mix = pos_v7 + pos_e5
    ok &= check("混在時の合算=5.85%", abs(open_risk_pct(pos_mix, B) - 5.85) < 1e-9)
    pos_nosl = [dict(notional=B * 0.30)]                      # SLなし建玉30%ノーショナル
    ok &= check("SLなし建玉は建玉額×10%で見積(=3.0%)", abs(open_risk_pct(pos_nosl, B) - 3.0) < 1e-9)

    print("== (b) 既定サイズでのSL到達損(解析値・PortfolioD median-3標準) ==")
    risks = sleeve_sl_risks()
    for k, v in risks.items():
        print(f"  {k:16s} {v:6.3f}%")
    ok &= check("E5 1レッグ(3.90%)だけで3%上限を超える(→既定MONITORの根拠)",
                risks["e5_per_leg"] > 3.0)
    ok &= check("v7+E-Monのフル月曜(3.90%)も3%を超える", risks["v7_full_week"] + risks["emon_full_week"] > 3.0)

    out = dict(all_pass=bool(ok), sleeve_sl_risk_pct=risks,
               cap=3.0, default_mode="MONITOR",
               note="analytic values from validated EA inputs; no new backtest claim")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "verify_risk_guard.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(("ALL PASS" if ok else "FAILURES PRESENT"), "->", path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
