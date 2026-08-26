#!/usr/bin/env python3
"""販売用EA候補の全数スクリーニング.

prop 側 (claude/mql-file-config-review-merge-uo5bx0) の手法を「販売用」の
基準で測り直す。prop 側は直近12ヶ月で選抜する EV ベット(耐久エッジを
主張しない)だったが、販売商品は購入者が数年使うため全期間の耐久性が要る。

判定基準(事前固定):
  - 全期間(最大15年)で評価。コストは往復で控除。
  - IS(前半60%) / OOS(後半40%) の双方でプラス
  - 全期間 t 値 >= 3.0 (476セル規模の多重検定に対し p<0.0013 = 期待誤検出0.6件)
  - 最低取引数 100
"""
import math, statistics as st
from collections import defaultdict
from fetch import fetch_daily

# (Yahoo, 表示名, 資産クラス)
UNIVERSE = [
    # --- FX majors / crosses (MT5でどの業者でも確実に扱える) ---
    ("USDJPY=X","USDJPY","fx"), ("EURJPY=X","EURJPY","fx"), ("GBPJPY=X","GBPJPY","fx"),
    ("AUDJPY=X","AUDJPY","fx"), ("NZDJPY=X","NZDJPY","fx"), ("CADJPY=X","CADJPY","fx"),
    ("CHFJPY=X","CHFJPY","fx"),
    ("EURUSD=X","EURUSD","fx"), ("GBPUSD=X","GBPUSD","fx"), ("AUDUSD=X","AUDUSD","fx"),
    ("NZDUSD=X","NZDUSD","fx"), ("USDCAD=X","USDCAD","fx"), ("USDCHF=X","USDCHF","fx"),
    ("EURGBP=X","EURGBP","fx"), ("EURAUD=X","EURAUD","fx"), ("GBPAUD=X","GBPAUD","fx"),
    # --- 指数CFD ---
    ("^N225","JP225","idx"), ("^GSPC","US500","idx"), ("^DJI","US30","idx"),
    ("^NDX","NAS100","idx"), ("^GDAXI","GER40","idx"), ("^FTSE","UK100","idx"),
    ("^HSI","HK50","idx"), ("^AXJO","AUS200","idx"),
    # --- 貴金属 / エネルギー ---
    ("GC=F","XAUUSD","met"), ("SI=F","XAGUSD","met"), ("PL=F","XPTUSD","met"),
    ("CL=F","USOIL","eng"), ("BZ=F","UKOIL","eng"),
]

# 往復コスト(名目比%)。スプレッド+スリッページ+1泊分のスワップ/金利を含む保守値。
COST = {"fx": 0.020, "idx": 0.030, "met": 0.050, "eng": 0.060}

MIN_TRADES = 100
T_STRICT = 3.5
T_MARGINAL = 3.0


def tstat(xs):
    n = len(xs)
    if n < 5:
        return 0.0
    s = st.pstdev(xs)
    return 0.0 if s == 0 else st.mean(xs) / (s / math.sqrt(n))


def dow_cell(rows, dow, direction, cost):
    """曜日 open-to-open。dow=0..4 (Mon..Fri)。翌営業日の寄りで決済。"""
    import datetime as _dt
    out = []
    for i in range(len(rows) - 1):
        d = _dt.date.fromisoformat(rows[i][0])
        if d.weekday() != dow:
            continue
        o0, o1 = rows[i][1], rows[i + 1][1]
        r = (o1 / o0 - 1.0) * 100.0 * direction - cost
        out.append((rows[i][0], r))
    return out


def season_cell(rows, month, direction, cost):
    """月次 L/S。その月の最初の営業日の寄り→翌月最初の営業日の寄り。"""
    firsts = {}
    for day, o, h, l, c in rows:
        key = day[:7]
        if key not in firsts:
            firsts[key] = (day, o)
    keys = sorted(firsts)
    out = []
    for i in range(len(keys) - 1):
        if int(keys[i][5:7]) != month:
            continue
        o0, o1 = firsts[keys[i]][1], firsts[keys[i + 1]][1]
        r = (o1 / o0 - 1.0) * 100.0 * direction - cost
        out.append((firsts[keys[i]][0], r))
    return out


def evaluate(series):
    if len(series) < MIN_TRADES:
        return None
    series = sorted(series)
    xs = [r for _, r in series]
    cut = int(len(xs) * 0.6)
    return {
        "n": len(xs), "mean": st.mean(xs), "t": tstat(xs),
        "is_mean": st.mean(xs[:cut]), "oos_mean": st.mean(xs[cut:]),
        "oos_n": len(xs) - cut,
        "wr": 100.0 * sum(1 for x in xs if x > 0) / len(xs),
        "pf": (sum(x for x in xs if x > 0) / abs(sum(x for x in xs if x < 0))
               if any(x < 0 for x in xs) else 99.0),
        "first": series[0][0], "last": series[-1][0],
    }


def main():
    data = {}
    for ysym, name, cls in UNIVERSE:
        try:
            data[name] = (fetch_daily(ysym), cls)
        except Exception as e:
            print(f"  ! {name}: {e}")
    print(f"取得: {len(data)}/{len(UNIVERSE)} 銘柄\n")

    cells = []
    dows = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for name, (rows, cls) in data.items():
        cost = COST[cls]
        for di, dn in enumerate(dows):
            for direction, ds in ((1, "L"), (-1, "S")):
                s = dow_cell(rows, di, direction, cost)
                e = evaluate(s)
                if e:
                    cells.append({"fam": "DOW", "sym": name, "cls": cls,
                                  "key": f"{dn}_{ds}", "series": s, **e})
        for m in range(1, 13):
            for direction, ds in ((1, "L"), (-1, "S")):
                s = season_cell(rows, m, direction, cost)
                e = evaluate(s)
                if e:
                    cells.append({"fam": "SEASON", "sym": name, "cls": cls,
                                  "key": f"M{m:02d}_{ds}", "series": s, **e})

    print(f"評価セル総数: {len(cells)}  (DOW / SEASON)")
    nd = sum(1 for c in cells if c["fam"] == "DOW")
    print(f"  DOW={nd}  SEASON={len(cells)-nd}")
    exp_fp = len(cells) * 0.0013
    print(f"  t>=3.0 の期待誤検出数: {exp_fp:.1f} 件\n")

    passed = [c for c in cells
              if c["t"] >= T_MARGINAL and c["is_mean"] > 0 and c["oos_mean"] > 0]
    passed.sort(key=lambda c: -c["t"])

    print("=" * 100)
    print("全期間t>=3.0 かつ IS/OOS 双方プラス のセル")
    print("=" * 100)
    print(f"{'族':<7}{'銘柄':<9}{'セル':<9}{'n':>5}{'t':>7}{'平均%':>8}"
          f"{'IS%':>8}{'OOS%':>8}{'勝率':>7}{'PF':>7}  期間")
    for c in passed:
        print(f"{c['fam']:<7}{c['sym']:<9}{c['key']:<9}{c['n']:>5}{c['t']:>7.2f}"
              f"{c['mean']:>8.3f}{c['is_mean']:>8.3f}{c['oos_mean']:>8.3f}"
              f"{c['wr']:>6.1f}%{c['pf']:>7.2f}  {c['first']}〜{c['last']}")
    print(f"\n通過 {len(passed)} セル / 期待誤検出 {exp_fp:.1f} 件")

    strict = [c for c in passed if c["t"] >= T_STRICT]
    print(f"うち t>=3.5(厳格): {len(strict)} セル\n")

    # 族としての一貫性: 銘柄クラス×セルキーで横断集計
    print("=" * 100)
    print("族の一貫性チェック(同じセルキーが複数銘柄で効いているか)")
    print("=" * 100)
    grp = defaultdict(list)
    for c in cells:
        grp[(c["fam"], c["key"], c["cls"])].append(c)
    rows_out = []
    for (fam, key, cls), lst in grp.items():
        if len(lst) < 3:
            continue
        allr = [r for c in lst for _, r in c["series"]]
        rows_out.append((tstat(allr), fam, key, cls, len(lst), st.mean(allr), len(allr)))
    rows_out.sort(reverse=True)
    print(f"{'t':>7}  {'族':<7}{'セル':<9}{'クラス':<6}{'銘柄数':>6}{'平均%':>9}{'n':>7}")
    for t, fam, key, cls, k, mu, n in rows_out[:15]:
        print(f"{t:>7.2f}  {fam:<7}{key:<9}{cls:<6}{k:>6}{mu:>9.4f}{n:>7}")

    import json
    json.dump([{k: v for k, v in c.items() if k != "series"} for c in cells],
              open("cells.json", "w"))
    return passed


if __name__ == "__main__":
    main()
