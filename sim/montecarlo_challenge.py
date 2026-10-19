#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montecarlo_challenge.py
=======================
FundedNext "Stellar 2-Step" ($100,000) チャレンジ通過確率モンテカルロ・シミュレータ

【このシミュレーションが「何であって、何でないか」】
  ・これは EA に実装したリスク管理（日次/累積ハードガード、固定%リスク、SL必須）
    のもとで、想定エッジ（勝率・RR）とコストを与えたときに、
    「日次5%/最大10%のドローダウン規則を一度も破らずに +8% に到達できる確率」を
    取引レベルで推計する確率シミュレーションである。
  ・これは "実ヒストリカル価格を用いたストラテジーテスター・バックテスト" ではない。
    実価格BT・ウォークフォワードは MT5 ストラテジーテスターで別途実施する前提
    （手順は docs/03_validation_report.md に記載）。
  ・目的は2つ:
      (1) リスクガードが機能し、いかなる想定エッジでも「失格(退場)」確率を
          極小化することの実証（= 設計原則#1の検証）。
      (2) 通過確率が想定エッジ(勝率/RR)にどう依存するかの感度分析（正直な合否提示）。

【主要モデル仮定】（すべてコード内に明示。レポートにも転記）
  ・口座: 初期残高 100,000、Phase1 目標 108,000 (+8%)。
  ・日次損失規則: 当日 equity が「日初 equity − 5,000」を割れば失格（含み損・手数料込み）。
    → EA ガードは 4,000 (=4%) で当日全決済・新規停止する想定を反映。
  ・最大損失規則: equity が 90,000 を割れば失格（静的フロア）。
    → EA ガードは 92,000 (=−8%) で全決済・EA停止する想定を反映。
  ・1トレードのリスク = risk_pct × 現在 equity（固定%リスク）。
  ・コスト: 1トレードあたりドルコスト = lots × 往復コスト。
    lots は SL 距離(pips)とpip価値から算出。コストは純損益に必ず計上。
  ・スリッページ・テール: 確率 p_slip で損失が k 倍に拡大（ギャップ/急変の保守的モデル）。
  ・min 取引日数 5 を満たすため、到達しても最低5営業日は経過させる。
"""

import random
import json
import os

# ----------------------------------------------------------------------------
# 口座・規則パラメータ（FundedNext Stellar 2-Step / $100K）
# ----------------------------------------------------------------------------
INITIAL_BALANCE      = 100_000.0
PROFIT_TARGET        = 108_000.0     # Phase1 +8%
DAILY_LOSS_LIMIT     = 5_000.0       # 5% 失格ライン（日初equity基準・含み損込み）
MAX_LOSS_FLOOR       = 90_000.0      # 10% 静的フロア（割れば失格）
MIN_TRADING_DAYS     = 5

# EA 内部ハードガード（規則の手前で止める安全マージン）
EA_DAILY_STOP        = 4_000.0       # 当日 −4% で全決済＆当日新規停止
EA_EQUITY_FLOOR      = 92_000.0      # 累積 −8% で全決済＆EA停止

# ----------------------------------------------------------------------------
# 取引・コスト・エッジのパラメータ（EAの既定値に整合）
# ----------------------------------------------------------------------------
RISK_PCT             = 0.004         # 1トレード 0.4% リスク
MAX_TRADES_PER_DAY   = 3             # 1日最大トレード数
SL_PIPS              = 28.0          # 平均SL距離(pips) EURUSD想定
PIP_VALUE_PER_LOT    = 10.0          # EURUSD: 1.0 lot = $10/pip
RR                   = 1.8           # 利確/損切り比（純額ベースの目標）

# コスト: 「保守シナリオ($105/lot往復)」と「現実シナリオ($7/lot往復)」を両方評価。
COMM_RT_REALISTIC    = 7.0           # FX現実値（FundedNext raw近似）
COMM_RT_CONSERVATIVE = 105.0         # ユーザー指定の保守値
SLIPPAGE_PIPS        = 0.5           # 1トレードあたり平均スリッページ(往復, pips)

# テール（ギャップ/急変）
P_SLIP_TAIL          = 0.03          # 3% の損失トレードで損失拡大
TAIL_LOSS_MULT       = 2.0          # その場合 損失は 2.0R 相当（ガード越え試験）

# シミュレーション規模
N_SIMS               = 50_000
MAX_DAYS             = 90            # Phase1 の試行上限（営業日）
TRADES_LAMBDA        = 2.0          # 1日の平均シグナル数（上限 MAX_TRADES_PER_DAY）

RNG = random.Random(20260530)


def trade_cost_dollars(lots, comm_rt):
    """1トレードの往復ドルコスト = 手数料 + スリッページ(pips換算)。"""
    commission = lots * comm_rt
    slippage   = lots * SLIPPAGE_PIPS * PIP_VALUE_PER_LOT
    return commission + slippage


def simulate_one(win_rate, rr, comm_rt, sl_pips=SL_PIPS):
    """1チャレンジ(Phase1)をシミュレートし結果dictを返す。"""
    equity = INITIAL_BALANCE
    day = 0
    peak = equity

    while day < MAX_DAYS:
        day += 1
        day_start_equity = equity
        day_loss = 0.0  # 当日の確定損失（正の値=損失額）
        n_signals = min(MAX_TRADES_PER_DAY, RNG.randint(0, MAX_TRADES_PER_DAY) if RNG.random() < 0.5 else _poisson(TRADES_LAMBDA))

        for _ in range(n_signals):
            # --- EA ガード: 当日 −4% 到達なら新規停止 ---
            if day_loss >= EA_DAILY_STOP:
                break
            # --- EA ガード: 累積 −8% フロアなら停止 ---
            if equity <= EA_EQUITY_FLOOR:
                break

            # 固定%リスクでロット算出
            risk_dollars = RISK_PCT * equity
            lots = risk_dollars / (sl_pips * PIP_VALUE_PER_LOT)
            cost = trade_cost_dollars(lots, comm_rt)

            if RNG.random() < win_rate:
                pnl = rr * risk_dollars - cost          # 勝ち
            else:
                loss_mult = 1.0
                if RNG.random() < P_SLIP_TAIL:
                    loss_mult = TAIL_LOSS_MULT          # テール損失
                pnl = -(loss_mult * risk_dollars) - cost

            equity += pnl
            if pnl < 0:
                day_loss += -pnl

            peak = max(peak, equity)

            # --- 規則違反判定（含み損込みを保守近似: 確定ベースで判定） ---
            if (day_start_equity - equity) >= DAILY_LOSS_LIMIT:
                return _result("FAIL_DAILY", equity, day)
            if equity <= MAX_LOSS_FLOOR:
                return _result("FAIL_MAXLOSS", equity, day)

            # --- 目標到達 ---
            if equity >= PROFIT_TARGET and day >= MIN_TRADING_DAYS:
                return _result("PASS", equity, day)

        # 目標到達済みだが最低取引日数未達 → 翌日以降も最小取引で消化
        if equity >= PROFIT_TARGET and day >= MIN_TRADING_DAYS:
            return _result("PASS", equity, day)

    status = "PASS" if (equity >= PROFIT_TARGET and day >= MIN_TRADING_DAYS) else "TIMEOUT"
    return _result(status, equity, day)


def _poisson(lmbda):
    """軽量ポアソン乱数（Knuth）。"""
    import math
    L = math.exp(-lmbda)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= RNG.random()
        if p <= L:
            return k - 1


def _result(status, equity, day):
    return {"status": status, "equity": equity, "days": day}


def run_grid(comm_rt, label, sl_pips=SL_PIPS):
    """勝率×RR のグリッドで通過/失格確率を集計。"""
    win_rates = [0.35, 0.40, 0.45, 0.50, 0.55]
    rrs       = [RR]  # RR は固定（EA既定）。勝率感度を主に見る。
    grid = []
    for wr in win_rates:
        for rr in rrs:
            counts = {"PASS": 0, "FAIL_DAILY": 0, "FAIL_MAXLOSS": 0, "TIMEOUT": 0}
            days_to_pass = []
            for _ in range(N_SIMS):
                r = simulate_one(wr, rr, comm_rt, sl_pips)
                counts[r["status"]] += 1
                if r["status"] == "PASS":
                    days_to_pass.append(r["days"])
            n = float(N_SIMS)
            avg_days = (sum(days_to_pass) / len(days_to_pass)) if days_to_pass else None
            grid.append({
                "win_rate": wr,
                "rr": rr,
                "expectancy_R": round(wr * rr - (1 - wr), 4),
                "pass_pct": round(100 * counts["PASS"] / n, 2),
                "fail_daily_pct": round(100 * counts["FAIL_DAILY"] / n, 3),
                "fail_maxloss_pct": round(100 * counts["FAIL_MAXLOSS"] / n, 3),
                "timeout_pct": round(100 * counts["TIMEOUT"] / n, 2),
                "avg_days_to_pass": round(avg_days, 1) if avg_days else None,
            })
    return {"label": label, "comm_rt": comm_rt, "sl_pips": sl_pips, "grid": grid}


def main():
    out = {
        "config": {
            "INITIAL_BALANCE": INITIAL_BALANCE,
            "PROFIT_TARGET": PROFIT_TARGET,
            "RISK_PCT": RISK_PCT,
            "RR": RR,
            "SL_PIPS": SL_PIPS,
            "MAX_TRADES_PER_DAY": MAX_TRADES_PER_DAY,
            "EA_DAILY_STOP": EA_DAILY_STOP,
            "EA_EQUITY_FLOOR": EA_EQUITY_FLOOR,
            "N_SIMS": N_SIMS,
            "TAIL": {"p": P_SLIP_TAIL, "mult": TAIL_LOSS_MULT},
        },
        "scenarios": [
            run_grid(COMM_RT_REALISTIC, "現実コスト $7/lot 往復 / SL28pips", sl_pips=28.0),
            run_grid(COMM_RT_CONSERVATIVE, "保守コスト $105/lot 往復 / SL28pips", sl_pips=28.0),
            run_grid(COMM_RT_CONSERVATIVE, "保守コスト $105/lot 往復 / SL60pips(スイング化で緩和)", sl_pips=60.0),
        ],
    }
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    path = os.path.join(os.path.dirname(__file__), "results", "montecarlo_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # コンソール用サマリ
    for sc in out["scenarios"]:
        print(f"\n=== {sc['label']} (comm_rt=${sc['comm_rt']}/lot RT, SL={sc['sl_pips']}pips) ===")
        print(f"{'WR':>5} {'E[R]':>7} {'Pass%':>7} {'FailDay%':>9} {'FailMax%':>9} {'Timeout%':>9} {'AvgDays':>8}")
        for g in sc["grid"]:
            print(f"{g['win_rate']*100:>4.0f}% {g['expectancy_R']:>7.3f} {g['pass_pct']:>6.2f}% "
                  f"{g['fail_daily_pct']:>8.3f}% {g['fail_maxloss_pct']:>8.3f}% "
                  f"{g['timeout_pct']:>8.2f}% {str(g['avg_days_to_pass']):>8}")
    print(f"\nJSON -> {path}")


if __name__ == "__main__":
    main()
