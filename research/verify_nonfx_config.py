#!/usr/bin/env python3
"""FN100k #14074882 RecentFit NonFX2 v1.00 の設定検証 (2026-08-15).

nonfx_screen.py の選抜結果と、焼き込みEA
mql/FN100k_14074882_RecentFit_NonFX2_v1.00.mq5 の既定値について、
「不備が無いか / 現状最適か」を検証するための再現スクリプト。

検証項目:
  1. 選抜再現性 — nonfx_screen.py の rev5 結果を再現できるか
  2. 窓外性能   — 選抜窓(直近12M)を除いた約9年での同一構成の成績
  3. タイミング感応度 — 研究の o2o 定義から窓をずらすとエッジが残るか
     (EAは取引所寄りではなく 4/6/8/10 UTC で建てるため、ここが要点)
  4. 損益分岐スプレッド — 各レッグが自分の執行コストを賄えるか
  5. 多重検定    — 選抜6セルの t を DOW族140検定で補正
  6. 災害SL影響  — 2.5*ATR(H1,24) を o2o セルに被せた場合の近似影響
  7. データ品質  — Yahoo の O=H=L=C 退化バー率(貴金属先物)
  8. ロット粒度  — 1ショットあたり想定元本が最小ロットに届くか

実行: python3 research/verify_nonfx_config.py
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import nonfx_screen as N

# EA の InpDowLegs をそのまま写したもの
YS = {"JP225": "^N225", "US500": "^GSPC", "HK50": "^HSI",
      "XAGUSD": "SI=F", "XPTUSD": "PL=F"}
LEGS = [("US500", "Tue", +1, 0.309), ("HK50", "Mon", +1, 0.209),
        ("HK50", "Thu", -1, 0.209), ("JP225", "Wed", +1, 0.140),
        ("XPTUSD", "Tue", +1, 0.072), ("XAGUSD", "Tue", +1, 0.060)]
# 選抜時の t スタット (nonfx_screen.py の一次候補出力より)
SEL_T = {"US500_Tue_L": (2.47, 52), "HK50_Mon_L": (3.57, 50),
         "HK50_Thu_S": (1.93, 50), "JP225_Wed_L": (2.02, 47),
         "XPTUSD_Tue_L": (1.66, 52), "XAGUSD_Tue_L": (2.56, 52)}
N_DOW_TESTS = 140          # rev5ユニバース14銘柄 x 5曜日 x 2方向
SHOTS = 4                  # ショット数(v1.00/v1.01 とも各レッグ4本)
INIT_BAL = 100000.0        # InpInitialBalance 推奨値
MULT = 1.0                 # v1.00 の InpMult 既定値
# v1.01 の稼働設定(XPT除外・逆ボラ再正規化・窓外基準の倍率)
V101_LEGS = [("US500", "Tue", +1, 0.333), ("HK50", "Mon", +1, 0.225),
             ("HK50", "Thu", -1, 0.225), ("JP225", "Wed", +1, 0.152),
             ("XAGUSD", "Tue", +1, 0.065)]
V101_BAL = 100000.0
V101_MULT = 0.72


def tag(sym, dow, dirn):
    return f"{sym}_{dow}_{'L' if dirn > 0 else 'S'}"


def hr(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def leg_series(rows, di, dirn, mode="o2o"):
    """曜日セルの日次リターン。mode で建玉窓をずらして感応度を見る。"""
    out = {}
    for i in range(1, len(rows) - 1):
        if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
            continue
        if mode == "o2o":                              # 研究セル定義(寄り→翌寄り)
            e, x = rows[i][1], rows[i + 1][1]
        elif mode == "c2c":                            # 終値→翌終値(数時間シフト)
            e, x = rows[i][4], rows[i + 1][4]
        elif mode == "o2c":                            # 日中のみ
            e, x = rows[i][1], rows[i][4]
        else:                                          # c2o: 前日終値→寄り
            e, x = rows[i - 1][4], rows[i][1]
        out[rows[i + 1][0]] = dirn * (x - e) / e
    return out


def perf(series, lo, hi):
    v = {d: x for d, x in series.items() if lo <= d <= hi}
    if not v:
        return None
    eq = pk = mdd = 0.0
    for d in sorted(v):
        eq += v[d]
        pk = max(pk, eq)
        mdd = min(mdd, eq - pk)
    yrs = (datetime.strptime(max(v), "%Y-%m-%d")
           - datetime.strptime(min(v), "%Y-%m-%d")).days / 365.25
    a = list(v.values())
    mu = sum(a) / len(a)
    sd = math.sqrt(sum((x - mu) ** 2 for x in a) / (len(a) - 1)) if len(a) > 1 else 0.0
    return dict(tot=eq, n=len(a), yrs=yrs, cagr=eq / yrs if yrs > 0 else 0.0,
                mdd=mdd, worst=min(a), t=mu / sd * math.sqrt(len(a)) if sd > 0 else 0.0)


def norm_sf(t):
    """両側p値 = 2*(1-Phi(t))。"""
    return math.erfc(t / math.sqrt(2.0))


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yr = (datetime.now(timezone.utc)
          .replace(year=datetime.now(timezone.utc).year - 1)).strftime("%Y-%m-%d")
    data = {s: N.fetch_daily(y) for s, y in YS.items()}
    px = {s: data[s][-1][4] for s in data}
    print(f"選抜窓 = {yr} .. {today}  /  Σw = {sum(w for *_, w in LEGS):.3f}")

    # ---------------------------------------------------------- 2. 窓外性能
    hr("[2] 窓外性能 — 選抜窓を除いた約9年で同じ構成を回した場合")
    print(f"{'レッグ':22s} {'選抜窓12M':>10s} {'窓外9年':>10s} {'窓外年率':>9s} {'窓外t':>7s} "
          f"{'10年計中の窓内比':>16s}")
    cells = []
    for sym, dow, dirn, w in LEGS:
        s = leg_series(data[sym], N.DOWS.index(dow), dirn)
        cells.append((sym, dow, dirn, w, s))
        a, i, o = perf(s, "0000", today), perf(s, yr, today), perf(s, "0000", yr)
        print(f"{tag(sym, dow, dirn):22s} {i['tot'] * 100:+9.2f}% {o['tot'] * 100:+9.2f}% "
              f"{o['cagr'] * 100:+8.2f}% {o['t']:7.2f} {i['tot'] / a['tot'] * 100:15.1f}%")
    port = defaultdict(float)
    for sym, dow, dirn, w, s in cells:
        for d, v in s.items():
            port[d] += w * v
    print(f"\n{'':22s} {'合計':>10s} {'年率':>9s} {'maxDD':>9s} {'最悪日':>8s} {'t':>7s}")
    for lab, p in (("選抜窓12M", perf(port, yr, today)),
                   ("窓外 約9年", perf(port, "0000", yr)),
                   ("全期間10年", perf(port, "0000", today))):
        print(f"{lab:22s} {p['tot'] * 100:+9.2f}% {p['cagr'] * 100:+8.2f}% "
              f"{p['mdd'] * 100:+8.2f}% {p['worst'] * 100:+7.2f}% {p['t']:7.2f}")
    print(f"\n※ EAのフロアは -{8.0:.0f}% (InpAccountFloorDDPct)。窓外maxDDと比較すること。")

    # -------------------------------------------- 3. タイミング感応度
    hr("[3] タイミング感応度 — 建玉窓をずらすとエッジは残るか")
    print("EAは取引所の寄りではなく 4/6/8/10 UTC で建てる。研究の o2o 定義から")
    print("窓がずれた場合にエッジが生き残るかを見る。\n")
    modes = ("o2o", "c2c", "o2c", "c2o")
    names = {"o2o": "o2o(研究定義)", "c2c": "c2c(窓シフト)",
             "o2c": "o2c(日中)", "c2o": "c2o(夜間)"}
    print(f"{'レッグ':22s} " + " ".join(f"{names[m]:>19s}" for m in modes))
    print(f"{'':22s} " + " ".join(f"{'12M':>9s}{'窓外':>10s}" for m in modes))
    agg = {m: [0.0, 0.0] for m in modes}
    for sym, dow, dirn, w in LEGS:
        row = f"{tag(sym, dow, dirn):22s} "
        for m in modes:
            s = leg_series(data[sym], N.DOWS.index(dow), dirn, m)
            i = sum(v for d, v in s.items() if d >= yr)
            o = sum(v for d, v in s.items() if d < yr)
            agg[m][0] += w * i
            agg[m][1] += w * o
            row += f" {i * 100:+8.1f}%{o * 100:+9.1f}%"
        print(row)
    print("-" * 100)
    print(f"{'合成(mult 1.0)':22s} "
          + " ".join(f" {agg[m][0] * 100:+8.1f}%{agg[m][1] / 9 * 100:+7.1f}%/y" for m in modes))

    # ------------------------------------------ 4. 損益分岐スプレッド
    hr("[4] 損益分岐スプレッド — 1レッグ日あたり往復1回・年52回")
    print("コスト(往復) = (スプレッド/価格) x w x 52。これが寄与を食い切る水準を示す。\n")
    print(f"{'レッグ':22s} {'価格':>10s} {'w':>6s} {'窓外寄与/年':>11s} {'BE(窓外)':>11s} "
          f"{'窓内寄与/年':>11s} {'BE(窓内)':>11s}")
    for sym, dow, dirn, w in LEGS:
        s = leg_series(data[sym], N.DOWS.index(dow), dirn)
        co = perf(s, "0000", yr)['cagr']
        ci = perf(s, yr, today)['cagr']
        u = "pt" if sym in ("US500", "HK50", "JP225") else "$"
        print(f"{tag(sym, dow, dirn):22s} {px[sym]:10.1f} {w:6.3f} {w * co * 100:+10.3f}% "
              f"{co / 52 * px[sym]:9.2f}{u:2s} {w * ci * 100:+10.3f}% {ci / 52 * px[sym]:9.2f}{u:2s}")
    print("\n※ BE = break-even スプレッド。デモ実測値がこれを超えるレッグは期待値が負。")

    # ----------------------------------------------------- 5. 多重検定
    hr("[5] 多重検定 — 選抜6セルの t を DOW族140検定で補正")
    print(f"{'レッグ':22s} {'t':>6s} {'素p':>9s} {'期待偽陽性件数':>15s} {'Bonferroni p':>13s}")
    for sym, dow, dirn, _ in LEGS:
        k = tag(sym, dow, dirn)
        t, _n = SEL_T[k]
        p = norm_sf(t)
        print(f"{k:22s} {t:6.2f} {p:9.4f} {N_DOW_TESTS * p:14.2f}件 "
              f"{min(1.0, N_DOW_TESTS * p):13.3f}")
    lo, hi = 0.0, 6.0
    for _ in range(60):                       # 帰無下での最大|t|期待値
        mid = (lo + hi) / 2
        if norm_sf(mid) > 1.0 / N_DOW_TESTS:
            lo = mid
        else:
            hi = mid
    print(f"\n帰無仮説下で140検定の最大|t|期待値 ≈ {lo:.2f}")

    # ------------------------------------------------------ 6. 災害SL
    hr("[6] 災害SL — 2.5*ATR(H1,24) を o2o セルに被せた近似影響")
    print("ATR(H1,24)=直近24本の時間足TR平均 ≒ 平均時間レンジ。日次レンジのおよそ")
    print("0.5倍が 2.5*ATR に相当する(23時間セッションのCFDの場合)。")
    print("研究セルにSLは無いため、EAのSLはそのままパリティ差になる。\n")
    for k, lab in ((0.5, "k=0.5 (MT5 23hセッション想定)"), (0.9, "k=0.9 (実測上限)")):
        print(f"--- SL距離 = 日次レンジ x {k} : {lab} ---")
        print(f"{'レッグ':22s} {'SL距離':>7s} {'接触率':>7s} {'12M SLなし':>11s}{'SLあり':>9s}"
              f"{'窓外/年 なし':>12s}{'あり':>9s}")
        ai = bi = ao = bo = 0.0
        for sym, dow, dirn, w in LEGS:
            rows = data[sym]
            di = N.DOWS.index(dow)
            rng = [(r[2] - r[3]) / r[3] for r in rows[-500:] if r[3] > 0 and r[2] > r[3]]
            slp = k * statistics.median(rng)
            hits = tot = 0
            x_i = y_i = x_o = y_o = 0.0
            for i in range(len(rows) - 1):
                if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
                    continue
                e, x = rows[i][1], rows[i + 1][1]
                raw = dirn * (x - e) / e
                if dirn > 0:
                    hit = min(rows[i][3], rows[i + 1][3]) <= e * (1 - slp)
                else:
                    hit = max(rows[i][2], rows[i + 1][2]) >= e * (1 + slp)
                tot += 1
                hits += hit
                if rows[i + 1][0] >= yr:
                    x_i += raw; y_i += -slp if hit else raw
                else:
                    x_o += raw; y_o += -slp if hit else raw
            ai += w * x_i; bi += w * y_i; ao += w * x_o; bo += w * y_o
            print(f"{tag(sym, dow, dirn):22s} {slp * 100:6.2f}% {hits / tot * 100:6.1f}% "
                  f"{x_i * 100:+10.1f}%{y_i * 100:+8.1f}%{x_o / 9 * 100:+11.1f}%{y_o / 9 * 100:+8.1f}%")
        print(f"{'合成 (mult 1.0)':22s} {'':7s} {'':7s} {ai * 100:+10.1f}%{bi * 100:+8.1f}%"
              f"{ao / 9 * 100:+11.1f}%{bo / 9 * 100:+8.1f}%\n")

    # -------------------------------------------------- 7. データ品質
    hr("[7] データ品質 — Yahoo の O=H=L=C 退化バー")
    print("退化バー = 気配ではなく清算値1点しか返っていないバー。o2o は「寄り」を")
    print("使うため、退化バーが多い系列のセルは定義どおりの取引を測れていない。\n")
    for sym in ("XPTUSD", "XAGUSD", "US500", "HK50", "JP225"):
        rows = data[sym]
        deg = sum(1 for r in rows if r[2] == r[3])
        dows = [d for s, d, _dir, _w in LEGS if s == sym]
        line = (f"{sym:8s} bars={len(rows):5d}  O=H=L=C {deg:5d} ({deg / len(rows) * 100:5.1f}%)")
        for dow in set(dows):
            di = N.DOWS.index(dow)
            bad = tot = bad12 = tot12 = 0
            for i in range(len(rows) - 1):
                if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
                    continue
                d = (rows[i][2] == rows[i][3]) or (rows[i + 1][2] == rows[i + 1][3])
                tot += 1; bad += d
                if rows[i + 1][0] >= yr:
                    tot12 += 1; bad12 += d
            line += (f" | {dow}セル: 退化を含む取引 {bad}/{tot} ({bad / tot * 100:.0f}%)"
                     f" 窓内 {bad12}/{tot12} ({bad12 / max(tot12, 1) * 100:.0f}%)")
        print(line)

    # -------------------------------------------------- 8. ロット粒度
    hr("[8] ロット粒度 — 1ショットの想定元本が最小ロットに届くか (v1.01設定)")
    print(f"レッグ想定元本 = InpInitialBalance({V101_BAL:.0f}) x w x mult({V101_MULT})")
    print("最小取引額 = 最小ロット x 契約サイズ x 価格。")
    print("v1.00 は 1ショットが最小取引額に届かないと無音でレッグが消えた。")
    print("v1.01 は RefreshShots() がショット数を自動的に減らして建玉サイズを確保する。\n")
    specs = {"US500": [(1, 0.01), (1, 0.1)], "HK50": [(1, 0.01), (1, 0.1)],
             "JP225": [(1, 0.01), (1, 0.1)],
             "XAGUSD": [(1000, 0.01), (5000, 0.01)]}
    print(f"{'レッグ':22s} {'契約':>7s} {'最小ロ':>7s} {'最小取引額$':>12s} "
          f"{'v1.00(4shot)':>14s} {'v1.01 実効shot':>15s}")
    for sym, dow, dirn, w in V101_LEGS:
        full = V101_BAL * w * V101_MULT
        for cs, ml in specs[sym]:
            # HK50/JP225 は現地通貨建て。USD換算の概算レートを当てる。
            fx = {"HK50": 1 / 7.8, "JP225": 1 / 148.0}.get(sym, 1.0)
            mn = ml * cs * px[sym] * fx
            v100 = "OK" if mn <= full / SHOTS else "✗ 消える"
            n = SHOTS                       # v1.01: 建つまでショット数を減らす
            while n > 1 and full / n < mn:
                n -= 1
            v101 = f"{n} shot" if full / n >= mn else "✗ 建たない"
            print(f"{tag(sym, dow, dirn):22s} {cs:7d} {ml:7.2f} {mn:12.0f} "
                  f"{v100:>14s} {v101:>15s}")
    print("\n※ 契約サイズ/最小ロット/ステップは FN のデモ気配で要確認(ここは候補値)。")
    print("※ EA起動時の [INIT SIZE] ログに実値が出るので、そちらで最終確認すること。")

    # ------------------------------------------------ 9. v1.00 vs v1.01
    hr("[9] v1.00 vs v1.01 — 最適化の効果")
    v101 = [("US500", "Tue", +1, 0.333), ("HK50", "Mon", +1, 0.225),
            ("HK50", "Thu", -1, 0.225), ("JP225", "Wed", +1, 0.152),
            ("XAGUSD", "Tue", +1, 0.065)]

    def compose(legs, sl_k=None):
        """sl_k を与えると k*ATR(D1,14) の災害SLを被せる(日足OHLC近似)。"""
        p = defaultdict(float)
        for sym, dow, dirn, w in legs:
            rows = data[sym]
            di = N.DOWS.index(dow)
            at = N.atr14(rows)
            for i in range(len(rows) - 1):
                if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
                    continue
                e = rows[i][1]
                raw = dirn * (rows[i + 1][1] - e) / e
                if sl_k is None or at[i] is None or at[i] <= 0:
                    p[rows[i + 1][0]] += w * raw
                    continue
                sl = sl_k * at[i] / e
                hit = ((min(rows[i][3], rows[i + 1][3]) <= e * (1 - sl)) if dirn > 0
                       else (max(rows[i][2], rows[i + 1][2]) >= e * (1 + sl)))
                p[rows[i + 1][0]] += w * (-sl if hit else raw)
        return p

    def rule08(s):
        """0.8x 校正規則: 最悪日>=-4% かつ maxDD>=-8% を満たす最大倍率 x 0.8。"""
        m, best = 0.05, 0.0
        while m <= 6.0:
            if s['worst'] * m >= -0.04 and s['mdd'] * m >= -0.08:
                best = m
            else:
                break
            m = round(m + 0.05, 2)
        return round(0.8 * best, 2)

    print(f"{'':30s} {'mult':>6s} {'窓外maxDD':>10s} {'窓外年率':>9s} {'選抜窓12M':>10s} {'フロア-8%':>10s}")
    for lab, legs, k, fixed in (
            ("v1.00 (6セル・SLなし相当)", LEGS, None, 1.00),
            ("v1.01 (5セル・SL 5xATR(D1))", v101, 5.0, 0.72)):
        p = compose(legs, k)
        o = perf(p, "0000", yr)
        i = perf(p, yr, today)
        rule = rule08(o)
        print(f"{lab:30s} {fixed:6.2f} {o['mdd'] * fixed * 100:9.2f}% "
              f"{o['cagr'] * fixed * 100:8.2f}% {i['tot'] * fixed * 100:9.1f}% "
              f"{'突破' if o['mdd'] * fixed <= -0.08 else '余裕あり':>10s}")
        print(f"{'  (0.8x規則が出す倍率)':30s} {rule:6.2f}")
    print("\n※ v1.00 の mult 1.0 は自身の校正規則(0.68)から乖離しており、窓外DDがフロアを突破する。")


if __name__ == "__main__":
    main()
