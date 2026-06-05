#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montecarlo_2phase.py
====================
ブリーフ手順5の明示的検証:
「日次/最大DDを一度も割らずに Phase1(+8%) → Phase2(+5%) を“連続で”通過できるか」を
モンテカルロで推計する。さらに、montecarlo_challenge.py の独立試行(i.i.d.)仮定の弱点を補う
【連敗の自己相関（レジーム持続）ストレス】を加える。

montecarlo_challenge.py を壊さず、こちらは「2フェーズ連結 + マルコフ的レジーム」を扱う上位版。

主な追加モデル仮定（すべて明示。レポートにも転記）:
  ・レジーム持続: 各トレード結果は2状態マルコフ連鎖で相関させる。
      - "good" レジームでは勝率 = base + regime_edge
      - "bad"  レジームでは勝率 = base - regime_edge
    レジーム継続確率 p_stay で滞留し、勝ち負けがクラスタリングする（=連敗が固まる）。
    regime_edge=0 なら i.i.d. に一致（後方互換チェック用）。
  ・2フェーズ: Phase1で+8%到達後、口座を$100,000にリセットしPhase2(+5%)を実行。
    どちらかで失格(日次/最大DD)したら全体FAIL。両方通過で SEQ_PASS。
  ・ガード/コスト/サイジングは EA と montecarlo_challenge.py に整合。
"""

import random
import json
import os

INITIAL_BALANCE   = 100_000.0
DAILY_LOSS_LIMIT  = 5_000.0       # 規則 5%（当日開始equity基準・含み損込み）
MAX_LOSS_FLOOR    = 90_000.0      # 規則 10% 静的フロア
MIN_TRADING_DAYS  = 5

EA_DAILY_STOP     = 4_000.0       # 当日 −4% 全決済＆新規停止
EA_EQUITY_FLOOR   = 92_000.0      # 累積 −8% 恒久停止

RISK_PCT          = 0.004
MAX_TRADES_PER_DAY= 3
PIP_VALUE_PER_LOT = 10.0
RR                = 1.8
SLIPPAGE_PIPS     = 0.5
P_SLIP_TAIL       = 0.03
TAIL_LOSS_MULT    = 2.0

N_SIMS            = 30_000
MAX_DAYS_P1       = 90
MAX_DAYS_P2       = 60            # Phase2は目標が緩い(+5%)分、上限も短め
TRADES_LAMBDA     = 2.0

# レジーム（自己相関）設定
P_STAY            = 0.80          # 同一レジーム継続確率（高いほど連敗が固まる）
REGIME_EDGE       = 0.10          # good/bad で勝率を ±0.10 振る

RNG = random.Random(20260530)


def _poisson(lmbda):
    import math
    L = math.exp(-lmbda); k = 0; p = 1.0
    while True:
        k += 1; p *= RNG.random()
        if p <= L:
            return k - 1


def run_phase(base_wr, rr, comm_rt, sl_pips, target_pct, max_days, state):
    """1フェーズを実行。state はレジーム状態を跨いで持続させるための可変辞書。
       戻り値: ("PASS"/"FAIL_DAILY"/"FAIL_MAXLOSS"/"TIMEOUT", days, equity)"""
    equity = INITIAL_BALANCE
    target = INITIAL_BALANCE * (1.0 + target_pct/100.0)
    day = 0
    while day < max_days:
        day += 1
        day_start_equity = equity
        day_loss = 0.0
        n_signals = min(MAX_TRADES_PER_DAY,
                        RNG.randint(0, MAX_TRADES_PER_DAY) if RNG.random() < 0.5 else _poisson(TRADES_LAMBDA))
        for _ in range(n_signals):
            if day_loss >= EA_DAILY_STOP:          # 当日ガード
                break
            if equity <= EA_EQUITY_FLOOR:          # 累積ガード
                break

            # --- レジーム遷移（マルコフ） ---
            if RNG.random() > P_STAY:
                state["regime"] = "bad" if state["regime"] == "good" else "good"
            wr = base_wr + (REGIME_EDGE if state["regime"] == "good" else -REGIME_EDGE)
            wr = min(0.95, max(0.05, wr))

            risk_dollars = RISK_PCT * equity
            lots = risk_dollars / (sl_pips * PIP_VALUE_PER_LOT)
            cost = lots * comm_rt + lots * SLIPPAGE_PIPS * PIP_VALUE_PER_LOT

            if RNG.random() < wr:
                pnl = rr * risk_dollars - cost
            else:
                mult = TAIL_LOSS_MULT if RNG.random() < P_SLIP_TAIL else 1.0
                pnl = -(mult * risk_dollars) - cost

            equity += pnl
            if pnl < 0:
                day_loss += -pnl

            if (day_start_equity - equity) >= DAILY_LOSS_LIMIT:
                return "FAIL_DAILY", day, equity
            if equity <= MAX_LOSS_FLOOR:
                return "FAIL_MAXLOSS", day, equity
            if equity >= target and day >= MIN_TRADING_DAYS:
                return "PASS", day, equity

        if equity >= target and day >= MIN_TRADING_DAYS:
            return "PASS", day, equity

    return ("PASS" if (equity >= target and day >= MIN_TRADING_DAYS) else "TIMEOUT"), day, equity


def run_grid(comm_rt, label, sl_pips):
    win_rates = [0.40, 0.45, 0.50, 0.55]
    grid = []
    for wr in win_rates:
        c = {"SEQ_PASS": 0, "P1_FAIL_DD": 0, "P2_FAIL_DD": 0, "TIMEOUT": 0}
        seq_days = []
        for _ in range(N_SIMS):
            state = {"regime": "good" if RNG.random() < 0.5 else "bad"}
            s1, d1, _ = run_phase(wr, RR, comm_rt, sl_pips, 8.0, MAX_DAYS_P1, state)
            if s1 in ("FAIL_DAILY", "FAIL_MAXLOSS"):
                c["P1_FAIL_DD"] += 1; continue
            if s1 == "TIMEOUT":
                c["TIMEOUT"] += 1; continue
            # Phase1通過 → Phase2（レジーム状態は継続させる＝悪地合いの連続も再現）
            s2, d2, _ = run_phase(wr, RR, comm_rt, sl_pips, 5.0, MAX_DAYS_P2, state)
            if s2 in ("FAIL_DAILY", "FAIL_MAXLOSS"):
                c["P2_FAIL_DD"] += 1; continue
            if s2 == "TIMEOUT":
                c["TIMEOUT"] += 1; continue
            c["SEQ_PASS"] += 1
            seq_days.append(d1 + d2)
        n = float(N_SIMS)
        avg = round(sum(seq_days)/len(seq_days), 1) if seq_days else None
        grid.append({
            "win_rate": wr,
            "seq_pass_pct": round(100*c["SEQ_PASS"]/n, 2),
            "p1_fail_dd_pct": round(100*c["P1_FAIL_DD"]/n, 3),
            "p2_fail_dd_pct": round(100*c["P2_FAIL_DD"]/n, 3),
            "any_dd_fail_pct": round(100*(c["P1_FAIL_DD"]+c["P2_FAIL_DD"])/n, 3),
            "timeout_pct": round(100*c["TIMEOUT"]/n, 2),
            "avg_days_seq_pass": avg,
        })
    return {"label": label, "comm_rt": comm_rt, "sl_pips": sl_pips, "grid": grid}


def main():
    out = {
        "config": {
            "N_SIMS": N_SIMS, "RISK_PCT": RISK_PCT, "RR": RR,
            "regime": {"P_STAY": P_STAY, "REGIME_EDGE": REGIME_EDGE,
                       "note": "2状態マルコフで連敗をクラスタリング。Phase間でレジーム継続。"},
            "guards": {"EA_DAILY_STOP": EA_DAILY_STOP, "EA_EQUITY_FLOOR": EA_EQUITY_FLOOR},
            "tail": {"p": P_SLIP_TAIL, "mult": TAIL_LOSS_MULT},
        },
        "scenarios": [
            run_grid(7.0,   "現実コスト $7/lot / SL28pips / 連敗相関あり", 28.0),
            run_grid(105.0, "保守コスト $105/lot / SL60pips / 連敗相関あり", 60.0),
        ],
    }
    path = os.path.join(os.path.dirname(__file__), "results", "montecarlo_2phase_results.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    for sc in out["scenarios"]:
        print(f"\n=== {sc['label']} (comm=${sc['comm_rt']}/lot, SL={sc['sl_pips']}pips) ===")
        print(f"{'WR':>5} {'SeqPass%':>9} {'P1failDD%':>10} {'P2failDD%':>10} {'AnyDDfail%':>11} {'Timeout%':>9} {'AvgDays':>8}")
        for g in sc["grid"]:
            print(f"{g['win_rate']*100:>4.0f}% {g['seq_pass_pct']:>8.2f}% "
                  f"{g['p1_fail_dd_pct']:>9.3f}% {g['p2_fail_dd_pct']:>9.3f}% "
                  f"{g['any_dd_fail_pct']:>10.3f}% {g['timeout_pct']:>8.2f}% "
                  f"{str(g['avg_days_seq_pass']):>8}")
    print(f"\nJSON -> {path}")


if __name__ == "__main__":
    main()
