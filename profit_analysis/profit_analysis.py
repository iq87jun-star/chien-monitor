#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スプレッドシートの商品データから利益商品を抽出し、
指定予算を投入した場合の見込み利益（合計利益が最大になる配分=方針A）を算出する。

使い方:
    python profit_analysis.py [CSVパス] [--budget 300000]

CSV想定カラム（--col-* で実際の列名に読み替え可能）:
    商品名 / 販売額 / 手数料 / 仕入れ値 / 仕入れ可能数(任意)

計算ロジック:
    1個利益 = 販売額 - 仕入れ値 - 手数料
        手数料が「率(0<値<=1 もしくは '%' 付き)」の場合は 販売額 × 率 に換算。
    利益率 = 1個利益 / 仕入れ値
    予算配分(方針A): 仕入れコスト=仕入れ値×個数 の制約下で合計利益が最大になる
        構成を「上限あり/なしの整数ナップサックDP」で厳密に解く。
        仕入れ可能数が空欄の商品は上限なし(予算が許す限り)とみなす。
"""
import argparse
import csv
import math
import os
import sys


def parse_fee(fee_raw, sale):
    """手数料を金額に換算して返す。率(%)指定にも対応。"""
    if fee_raw is None:
        return 0.0
    s = str(fee_raw).strip()
    if s == "":
        return 0.0
    is_pct = s.endswith("%")
    s = s.rstrip("%").replace(",", "").strip()
    if s == "":
        return 0.0
    v = float(s)
    if is_pct:                       # 例: "10%"
        return sale * v / 100.0
    if 0 < v <= 1:                   # 例: 0.12 → 率とみなす
        return sale * v
    return v                         # それ以外は金額


def to_number(x):
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_rows(path, cols):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader], reader.fieldnames


def analyze(path, budget, cols):
    rows, header = load_rows(path, cols)
    products, excluded = [], []

    for i, r in enumerate(rows, start=2):  # 2 = ヘッダ次の行
        name = (r.get(cols["name"]) or "").strip()
        sale = to_number(r.get(cols["sale"]))
        cost = to_number(r.get(cols["cost"]))
        fee_raw = r.get(cols["fee"])
        cap_raw = to_number(r.get(cols["cap"])) if cols["cap"] in (header or []) else None

        # --- 欠損・異常値の除外 ---
        if name == "" and sale is None and cost is None:
            excluded.append((f"行{i}", "全項目が空（テンプレ行）"))
            continue
        if sale is None:
            excluded.append((name or f"行{i}", "販売額が空"))
            continue
        if cost is None:
            excluded.append((name or f"行{i}", "仕入れ値が空"))
            continue
        if sale < 0 or cost < 0:
            excluded.append((name or f"行{i}", "価格がマイナス"))
            continue

        fee = parse_fee(fee_raw, sale)
        profit = sale - cost - fee
        if profit <= 0:
            excluded.append((name or f"行{i}",
                             f"手数料控除後の利益が0円以下 ({profit:,.1f}円)"))
            continue

        cap = int(cap_raw) if (cap_raw is not None and cap_raw > 0) else None
        margin = profit / cost if cost > 0 else float("inf")
        products.append({
            "name": name, "sale": sale, "cost": cost, "fee": fee,
            "profit": profit, "margin": margin, "cap": cap,
        })

    # 利益額の大きい順 → 利益率の高い順
    products.sort(key=lambda p: (-p["profit"], -p["margin"]))
    return products, excluded


def optimize(products, budget):
    """整数ナップサックDP（個数上限あり/なし）で合計利益が最大の配分を求める。"""
    B = int(budget)
    NEG = float("-inf")
    dp = [NEG] * (B + 1)
    dp[0] = 0.0
    # 各容量で「最後に入れた商品index」を記録して構成を復元
    pick = [-1] * (B + 1)
    used = [None] * (B + 1)  # 復元用: (前容量, 商品index)

    # 上限なし=unbounded、上限あり=bounded を統一的に扱う。
    # bounded はバイナリ展開で効率化。
    items = []  # (cost, profit, prod_index, max_count_or_None)
    for idx, p in enumerate(products):
        c = int(round(p["cost"]))
        if c <= 0:
            continue
        items.append((c, p["profit"], idx, p["cap"]))

    for c, prof, idx, cap in items:
        if cap is None:
            # unbounded: 昇順で更新
            for w in range(c, B + 1):
                if dp[w - c] != NEG and dp[w - c] + prof > dp[w]:
                    dp[w] = dp[w - c] + prof
                    used[w] = (w - c, idx)
        else:
            # bounded: バイナリ展開した塊を 0/1 ナップサックとして降順更新
            k = 1
            remaining = cap
            chunks = []
            while remaining > 0:
                take = min(k, remaining)
                chunks.append(take)
                remaining -= take
                k *= 2
            for cnt in chunks:
                cc, pp = c * cnt, prof * cnt
                for w in range(B, cc - 1, -1):
                    if dp[w - cc] != NEG and dp[w - cc] + pp > dp[w]:
                        dp[w] = dp[w - cc] + pp
                        # 復元は個数集計で行うため used は使わず後段で再構成
    # 最大利益の容量を探索
    best_w = max(range(B + 1), key=lambda w: dp[w] if dp[w] != NEG else NEG)
    best_profit = dp[best_w]

    # --- 構成の復元 ---
    # unbounded のみなら used で辿れるが、混在時の復元を安定させるため
    # 「全 unbounded」の標準ケースを再DPで個数復元する実装にする。
    counts = reconstruct(items, B, best_w)
    return best_profit, best_w, counts


def reconstruct(items, B, target_w):
    """target_w までの最適構成（商品index->個数）を再DPで復元。"""
    NEG = float("-inf")
    dp = [NEG] * (target_w + 1)
    dp[0] = 0.0
    choice = [None] * (target_w + 1)  # (商品index, この商品で進めた容量)
    # bounded を 1個単位の選択として辿れるよう、各容量で「直前に1個入れた商品」を記録
    # unbounded/bounded 両対応: 各商品ごとに残り上限を考慮した素直なDP
    # （規模が小さいので O(B * sum) で十分）
    # ここでは個数上限を尊重するため (容量) 状態に加え逐次貪欲復元を採用。
    # 実装簡潔化のため、unbounded は昇順、bounded はバイナリ展開で choice を記録。
    parent = [-1] * (target_w + 1)
    item_of = [-1] * (target_w + 1)
    for c, prof, idx, cap in items:
        if cap is None:
            for w in range(c, target_w + 1):
                if dp[w - c] != NEG and dp[w - c] + prof > dp[w]:
                    dp[w] = dp[w - c] + prof
                    parent[w] = w - c
                    item_of[w] = idx
        else:
            k = 1
            remaining = cap
            chunks = []
            while remaining > 0:
                take = min(k, remaining)
                chunks.append(take)
                remaining -= take
                k *= 2
            for cnt in chunks:
                cc, pp = c * cnt, prof * cnt
                for w in range(target_w, cc - 1, -1):
                    if dp[w - cc] != NEG and dp[w - cc] + pp > dp[w]:
                        dp[w] = dp[w - cc] + pp
                        parent[w] = w - cc
                        item_of[w] = idx
    counts = {}
    w = target_w
    # dp[target_w] が最良でない場合に備え、最良容量を選ぶ
    best_w = max(range(target_w + 1), key=lambda x: dp[x] if dp[x] != NEG else NEG)
    w = best_w
    guard = 0
    while w > 0 and parent[w] != -1:
        idx = item_of[w]
        counts[idx] = counts.get(idx, 0) + 1
        w = parent[w]
        guard += 1
        if guard > target_w + 5:
            break
    return counts


def yen(x):
    return f"{x:,.0f}円"


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("csv", nargs="?",
                    default=os.path.join(here, "data", "pokemon_products.csv"))
    ap.add_argument("--budget", type=float, default=300000)
    ap.add_argument("--col-name", default="商品名")
    ap.add_argument("--col-sale", default="販売額")
    ap.add_argument("--col-fee", default="手数料")
    ap.add_argument("--col-cost", default="仕入れ値")
    ap.add_argument("--col-cap", default="仕入れ可能数")
    args = ap.parse_args()

    cols = {"name": args.col_name, "sale": args.col_sale, "fee": args.col_fee,
            "cost": args.col_cost, "cap": args.col_cap}

    products, excluded = analyze(args.csv, args.budget, cols)

    print("=" * 78)
    print(f"入力: {args.csv}")
    print(f"予算: {yen(args.budget)}（方針A: 合計利益が最大になる配分）")
    print("=" * 78)

    print("\n■ 利益商品一覧（利益額の大きい順 → 利益率の高い順）")
    print(f"{'商品名':<14}{'仕入れ値':>10}{'販売額':>11}{'手数料':>11}"
          f"{'1個利益':>11}{'利益率':>9}")
    print("-" * 78)
    for p in products:
        print(f"{p['name']:<14}{p['cost']:>10,.0f}{p['sale']:>11,.0f}"
              f"{p['fee']:>11,.1f}{p['profit']:>11,.1f}{p['margin']*100:>8.1f}%")

    print("\n■ 除外した商品・行")
    if excluded:
        for name, reason in excluded:
            print(f"  - {name}: {reason}")
    else:
        print("  なし")

    best_profit, used_budget, counts = optimize(products, args.budget)
    leftover = args.budget - used_budget

    print("\n" + "=" * 78)
    print(f"■ {yen(args.budget)}投入時の最適仕入れ内訳（方針A）")
    print("=" * 78)
    print(f"{'商品名':<14}{'単価(仕入れ)':>12}{'個数':>6}{'投入額':>12}"
          f"{'見込み利益':>13}")
    print("-" * 78)
    total_cost = 0.0
    total_profit = 0.0
    # 利益額順で表示
    for idx in sorted(counts, key=lambda i: -products[i]["profit"]):
        p = products[idx]
        n = counts[idx]
        cost_sum = p["cost"] * n
        prof_sum = p["profit"] * n
        total_cost += cost_sum
        total_profit += prof_sum
        print(f"{p['name']:<14}{p['cost']:>12,.0f}{n:>6}{cost_sum:>12,.0f}"
              f"{prof_sum:>13,.1f}")
    print("-" * 78)
    print(f"{'合計':<14}{'':>12}{'':>6}{total_cost:>12,.0f}{total_profit:>13,.1f}")
    print(f"\n投入額合計   : {yen(total_cost)}")
    print(f"端数（未使用）: {yen(leftover)}  ※最安商品の仕入れ値未満のため使用不可")
    print(f"見込み利益   : {yen(total_profit)}")
    if total_cost > 0:
        print(f"投資利益率(ROI): {total_profit / total_cost * 100:.1f}%"
              f"（投入額ベース） / {total_profit / args.budget * 100:.1f}%（予算30万ベース）")


if __name__ == "__main__":
    main()
