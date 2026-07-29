#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
operator_roi.py — 運営参入(買収/新規)の費用対効果 (docs/178)
=============================================================

docs/174 の単体経済性(unit_economics)に**集客コスト CAC**を加え、
docs/177 の実勢買収価格に対する回収期間・ROI を決定論EVで算出する。

【docs/174 からの拡張点】
  ・CAC(獲得単価): 初回購入者1人の獲得に要する広告+アフィ実費。
    docs/175 の相場感 ¥15,000〜40,000/購入 → 基準 ¥25,000($159)。
    再購入(rebuy)はオーガニックとみなし CAC 不要。
  ・月間購入者数 N をパラメータ化(docs/174 は300固定)。
    定常月次利益 ≈ N × 顧客1人あたり生涯マージン − 固定OPEX。
    ⚠ これは「成熟後のランレート」であり、docs/174 のMC(最初の24ヶ月平均)より厳しい。
      s=0 では両者が ~3% で一致するが、s>0 では乖離する: 序盤は参加費が先行して
      黒字に見え、sharp への支払い負債が後から積み上がるため(例: defended s=2%
      N=300 は MC24ヶ月平均 +¥1,215万/月 に対し成熟ランレート −¥71万/月)。
      回収期間・ROI 判定には保守的な成熟ランレートを使うのが正しい。
      「初年度黒字」は成功の証拠にならない——プロップ運営が突然死する構造そのもの。

【出力】
  1. CAC込みの損益分岐 sharp 比率 s*(docs/174 の s* は CAC 抜きで甘い)
  2. (シナリオ, s, N) ごとの月次利益
  3. docs/177 の実勢価格に対する回収月数・24ヶ月ROI

【何でないか】: 決定論EV。破綻確率は docs/174 のMCを参照。法務・PSP承継リスクは価格外。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operator_economics import (  # noqa: E402
    unit_economics, TRADER, SCENARIOS, OPEX_FIXED_M, USDJPY, jpy)

CAC_USD      = 25_000 / USDJPY          # 獲得単価/初回購入者 (¥25,000 基準)
CAC_GRID_JPY = [15_000, 25_000, 40_000]  # 感度用
N_GRID       = [100, 300, 600]           # 月間新規購入者数
S_GRID       = [0.00, 0.02, 0.03, 0.05]

# docs/177 実勢価格 (USD)
DEALS = {
    "シェル(法人+MT5)+自力立上げ": 45_000,
    "中堅チャレンジ型(稼働中)":     330_000,
    "Instant型(稼働中)":           650_000,
}
# シェル買収は稼働まで追加費用(サイト構築・初期マーケ等)を上乗せ
SHELL_EXTRA = 60_000


def margins(scen, cac_usd):
    sc = SCENARIOS[scen]
    u_r = unit_economics(TRADER["retail"])
    u_s = unit_economics(TRADER["sharp"], payout_mult=sc["sharp_payout_mult"],
                         hazard=sc["sharp_hazard"])
    m_r = u_r["margin"] - cac_usd   # CAC は初回獲得のみ
    m_s = u_s["margin"] - cac_usd
    s_star = m_r / (m_r - m_s) if m_s < 0 < m_r else (0.0 if m_r <= 0 else 1.0)
    return m_r, m_s, s_star


def monthly_profit(scen, s, n, cac_usd):
    m_r, m_s, _ = margins(scen, cac_usd)
    mix = (1 - s) * m_r + s * m_s
    return n * mix - OPEX_FIXED_M


def main():
    print("=" * 100)
    print(f"運営参入の費用対効果 (docs/178) — CAC込み決定論EV / USDJPY={USDJPY:.0f} / "
          f"基準CAC ¥25,000/初回購入者")
    print("=" * 100)

    # [1] CAC込み損益分岐 s*
    print("\n[1] CAC込みの損益分岐 sharp 比率 s* (docs/174 の CAC抜き s* との比較)")
    print(f"    {'シナリオ':<10} {'CAC':>10} {'retailマージン':>14} {'sharpマージン':>16} {'s*':>8}")
    rows_sstar = []
    for scen in SCENARIOS:
        for cac_jpy in CAC_GRID_JPY:
            m_r, m_s, s_star = margins(scen, cac_jpy / USDJPY)
            rows_sstar.append(dict(scen=scen, cac_jpy=cac_jpy, s_star=s_star,
                                   m_retail_jpy=m_r * USDJPY, m_sharp_jpy=m_s * USDJPY))
            print(f"    {scen:<10} ¥{cac_jpy:>8,} {jpy(m_r):>14} {jpy(m_s):>16} "
                  f"{s_star * 100:>7.2f}%")

    # [2] 月次利益グリッド (基準CAC)
    print(f"\n[2] 成熟ランレート月次利益 (基準CAC ¥25,000, 固定OPEX {jpy(OPEX_FIXED_M)}/月)"
          "\n    ⚠ 序盤24ヶ月の平均はこれより良く見える(参加費先行・sharp負債は後積み)")
    print(f"    {'シナリオ':<10} {'s':>5} | " + " | ".join(f"N={n:>4}/月" + " " * 6 for n in N_GRID))
    profit_grid = {}
    for scen in SCENARIOS:
        for s in S_GRID:
            vals = [monthly_profit(scen, s, n, CAC_USD) for n in N_GRID]
            profit_grid[(scen, s)] = vals
            print(f"    {scen:<10} {s * 100:>4.0f}% | "
                  + " | ".join(f"{jpy(v):>14}" for v in vals))

    # [3] 実勢価格に対する回収月数・24ヶ月ROI
    print("\n[3] docs/177 実勢価格に対する回収月数 / 24ヶ月ROI (基準CAC)")
    deal_rows = []
    for deal, price in DEALS.items():
        eff_price = price + (SHELL_EXTRA if "シェル" in deal else 0)
        print(f"\n  ◆ {deal}: 取得 {jpy(price)}"
              + (f" + 立上げ {jpy(SHELL_EXTRA)} = 実効 {jpy(eff_price)}" if "シェル" in deal else ""))
        print(f"    {'シナリオ':<10} {'s':>5} {'N':>6} {'月次利益':>14} {'回収月数':>8} {'24M-ROI':>9}")
        for scen in ("defended",):
            for s in S_GRID:
                for n in N_GRID:
                    p = monthly_profit(scen, s, n, CAC_USD)
                    payback = eff_price / p if p > 0 else float("inf")
                    roi24 = (24 * p - eff_price) / eff_price
                    deal_rows.append(dict(deal=deal, eff_price_jpy=eff_price * USDJPY,
                                          scen=scen, s=s, n=n,
                                          monthly_jpy=p * USDJPY,
                                          payback_m=(None if p <= 0 else payback),
                                          roi24=roi24))
                    pb = f"{payback:>7.1f}月" if p > 0 else "  回収不能"
                    print(f"    {scen:<10} {s * 100:>4.0f}% {n:>6} {jpy(p):>14} {pb:>8} "
                          f"{roi24 * 100:>8.0f}%")

    # 参考: 挑戦者側継続のEVアンカー (docs/46/47 標準ティア, 資本ほぼゼロ)
    trader_ev_year = 1_856_446 + 928_223
    print(f"\n[参考] 挑戦者側を続ける場合のEV: 約 ¥{trader_ev_year:,}/年 "
          "(docs/46/47 標準ティア PROP+INSTANT 合算・投下資本ほぼゼロ)")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "operator_roi_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"config": dict(USDJPY=USDJPY, CAC_GRID_JPY=CAC_GRID_JPY,
                                  N_GRID=N_GRID, S_GRID=S_GRID, DEALS_USD=DEALS,
                                  SHELL_EXTRA_USD=SHELL_EXTRA,
                                  trader_ev_year_jpy=trader_ev_year),
                   "s_star": rows_sstar, "deals": deal_rows},
                  f, ensure_ascii=False, indent=2)
    print(f"結果JSON: {out}")


if __name__ == "__main__":
    main()
