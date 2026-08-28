#!/usr/bin/env python3
"""GogoJungle インジケーターの「実際に何本売れているか」調査(2026-08-28 取得).

PRICING.md は価格しか見ていなかった。こちらは販売本数を見る。

データ源: 商品ページに出る「すでに N 人が利用中！」(累計購入者数)と「販売開始日」。
        両方が公開情報なので、N ÷ 経過月数 で 本/月 を復元できる。
        カウンタが出ていない商品は累計0本として扱う(1本の商品は「すでに 1 人」と表示される)。

  収集:  python3 volume_research.py --fetch   # 新着順8ページ→商品ページ→CSV
  分析:  python3 volume_research.py           # volume_data_20260828.csv を集計
"""
import csv
import os
import statistics as st
import sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "volume_data_20260828.csv")
ASOF = date(2026, 8, 28)

BANDS = [
    (1, 3000, "〜2,999円"),
    (3000, 7000, "3,000〜6,999円"),
    (7000, 15000, "7,000〜14,999円"),
    (15000, 30000, "15,000〜29,999円"),
    (30000, 50000, "30,000〜49,999円"),
    (50000, 10**9, "50,000円〜"),
]


def fetch():
    """新着順の一覧から商品IDを集め、各商品ページを取得してCSVに落とす。"""
    import re
    import time
    import urllib.request

    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

    ids = set()
    for page in range(1, 9):
        h = get(f"https://www.gogojungle.co.jp/search?ctg=2&sort=no&page={page}")
        ids |= set(re.findall(r"/tools/indicators/(\d+)", h))
        time.sleep(1)

    rows = []
    for pid in sorted(ids, key=int):
        try:
            h = get(f"https://www.gogojungle.co.jp/tools/indicators/{pid}")
        except Exception:
            continue
        time.sleep(0.4)
        price = re.search(r"price-ui-v2__amount[^>]*>￥([\d,]+)<", h)
        start = re.search(
            r'販売開始日:</div>\s*<div class="row-content"[^>]*>\s*(\d{4}/\d{2}/\d{2})', h)
        if not (price and start):
            continue
        users = re.search(r"すでに\s*([\d,]+)\s*人が利用中", h)
        title = re.search(r"<title>(.*?) - ", h, re.S)
        y, m, d = map(int, start.group(1).split("/"))
        months = max(0.5, (ASOF - date(y, m, d)).days / 30.44)
        n = int(users.group(1).replace(",", "")) if users else 0
        rows.append({
            "id": pid,
            "price": int(price.group(1).replace(",", "")),
            "users": n,
            "start": start.group(1),
            "months": round(months, 1),
            "rate": round(n / months, 2),
            "name": (title.group(1).strip() if title else "")[:70],
        })

    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "price", "users", "start", "months", "rate", "name"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} 件を {CSV} に保存")


def load():
    with open(CSV, encoding="utf-8") as f:
        return [{**r, "price": int(r["price"]), "users": int(r["users"]),
                 "months": float(r["months"]), "rate": float(r["rate"])}
                for r in csv.DictReader(f) if int(r["price"]) > 0]


def summ(label, xs):
    if not xs:
        return
    rt = sorted(x["rate"] for x in xs)
    n = len(rt)
    q = lambda p: rt[min(n - 1, int(p * n))]
    print(f"{label:<28} n={n:>3}  10%{q(.10):5.2f}  25%{q(.25):5.2f}  "
          f"中央{st.median(rt):6.2f}  75%{q(.75):6.2f}  90%{q(.90):6.2f}")


def main():
    rows = load()
    mature = [r for r in rows if r["months"] >= 3]

    print("=" * 88)
    print(f"GogoJungle インジケーター 販売速度(本/月) — {ASOF} 時点 / 販売開始3ヶ月以上の {len(mature)} 件")
    print("=" * 88)
    summ("全体", mature)
    for lo, hi, label in BANDS:
        summ("  " + label, [r for r in mature if lo <= r["price"] < hi])

    zero = [r for r in mature if r["users"] == 0]
    few = [r for r in mature if r["users"] <= 3]
    print(f"\n累計0本: {len(zero)}/{len(mature)} ({len(zero)/len(mature)*100:.1f}%)"
          f"   累計3本以下: {len(few)}/{len(mature)} ({len(few)/len(mature)*100:.1f}%)")

    young = [r for r in rows if 3 <= r["months"] <= 9]
    print("\n" + "=" * 88)
    print(f"販売開始3〜9ヶ月の商品が、その間に積み上げた累計本数({len(young)}件)")
    print("=" * 88)
    for lo, hi, label in BANDS:
        xs = sorted(r["users"] for r in young if lo <= r["price"] < hi)
        if not xs:
            continue
        n = len(xs)
        print(f"  {label:<18} n={n:>2}  最小{xs[0]:>4}  25%{xs[n//4]:>4}  "
              f"中央{st.median(xs):>6.0f}  75%{xs[3*n//4]:>5}  最大{xs[-1]}")

    print("\n" + "=" * 88)
    print("自社商品と同じ価格帯の実例(販売開始3ヶ月以上・遅い順)")
    print("=" * 88)
    for lo, hi, label in [(3000, 7000, "環境計 4,980円"), (15000, 30000, "待ち伏せ 導入19,800円"),
                          (30000, 50000, "待ち伏せ 定価39,800円")]:
        xs = sorted([r for r in mature if lo <= r["price"] < hi and r["months"] <= 30],
                    key=lambda r: r["rate"])
        print(f"\n### {label} の帯  n={len(xs)}")
        for r in xs:
            print(f"  {r['rate']:>6.2f}本/月  {r['price']:>7,}円  累計{r['users']:>5}本 /"
                  f"{r['months']:>5.1f}ヶ月  {r['start']}  {r['name'][:40]}")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch()
    else:
        main()
