#!/usr/bin/env python3
"""[v1.02] 2つのレビュー(vqtxyw / qxapaj)の対立点を独立に裁定する。

争点:
  V(vqtxyw): catATR=2.5 は接触率42-59%で研究と別物 → 5.0*ATR(D1) へ。mult 0.72。XPT除外。
  Q(qxapaj): それは方法論誤り。正しくは36.8%でmaxDD半減 → 2.5据置。mult 1.0。XPT存置。

検証する仮説:
  H1. V の接触判定は決済後(翌日日中)の安値を含む二重計上ではないか
  H2. Q の「ギャップ突き抜けも -sd で止まる」は楽観ではないか
  H3. 両者とも ATR を当日バー込み(at[i])で引いており先読みではないか
  H4. Q は校正を選抜窓込みの全期間で行っており、窓外で見ると結論が変わらないか
"""
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import nonfx_screen as N

YS = {"JP225": "^N225", "US500": "^GSPC", "HK50": "^HSI",
      "XAGUSD": "SI=F", "XPTUSD": "PL=F"}
LEGS6 = [("US500", "Tue", +1, 0.309), ("HK50", "Mon", +1, 0.209),
         ("HK50", "Thu", -1, 0.209), ("JP225", "Wed", +1, 0.140),
         ("XPTUSD", "Tue", +1, 0.072), ("XAGUSD", "Tue", +1, 0.060)]

TODAY = datetime.utcnow().strftime("%Y-%m-%d")
YR = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")


def hr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def maxdd(series):
    eq, pk, mdd = 1.0, 1.0, 0.0
    for d in sorted(series):
        eq *= (1 + series[d])
        pk = max(pk, eq)
        mdd = min(mdd, eq / pk - 1)
    return mdd


def stats(series, lo, hi):
    s = {d: v for d, v in series.items() if lo <= d < hi}
    if not s:
        return dict(tot=0, cagr=0, mdd=0, worst=0, n=0)
    eq = 1.0
    for d in sorted(s):
        eq *= (1 + s[d])
    yrs = max(len(s) / 52.0, 1e-9)          # 週次セル → 52/年 換算
    days = (datetime.strptime(max(s), "%Y-%m-%d")
            - datetime.strptime(min(s), "%Y-%m-%d")).days or 1
    yrs = days / 365.25
    return dict(tot=eq - 1, cagr=(eq ** (1 / yrs) - 1) if yrs > 0.3 else eq - 1,
                mdd=maxdd(s), worst=min(s.values()), n=len(s))


# ---------------------------------------------------------------- 接触判定
def leg_returns(rows, atr, di, sgn, sl_d1, method):
    """sl_d1: SL距離を ATR_D1 の倍数で指定 (None=SLなし)。
    method: 'V'=決済後日中も含む / 'Q'=当日日中+ギャップも-sdで止まる /
            'X'=当日日中のみ、ギャップは翌寄りで実約定(悲観)"""
    out, hits, n = {}, 0, 0
    for i in range(len(rows) - 1):
        if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
            continue
        # H3: SLは建玉時(当日寄り)に決まる → 当日バーを含まない at[i-1] を使う
        a = atr[i - 1] if method == "X" else atr[i]
        if a is None or a <= 0:
            continue
        e = rows[i][1]
        x = rows[i + 1][1]
        r = sgn * (x - e) / e
        n += 1
        if sl_d1:
            sd = sl_d1 * a
            if method == "V":       # 翌日(決済後)の安値まで見る = 二重計上
                adv = min(rows[i][3], rows[i + 1][3]) if sgn > 0 else \
                      max(rows[i][2], rows[i + 1][2])
                hit = (e - adv) >= sd if sgn > 0 else (adv - e) >= sd
                if hit:
                    r = -sd / e
                    hits += 1
            elif method == "Q":     # 当日日中 + ギャップも -sd で止まる(楽観)
                adv = rows[i][3] if sgn > 0 else rows[i][2]
                if ((e - adv) >= sd if sgn > 0 else (adv - e) >= sd) or r < -sd / e:
                    r = -sd / e
                    hits += 1
            else:                   # 'X' 当日日中のみ。ギャップは翌寄りで実約定
                adv = rows[i][3] if sgn > 0 else rows[i][2]
                if (e - adv) >= sd if sgn > 0 else (adv - e) >= sd:
                    r = -sd / e
                    hits += 1
                # ギャップ突き抜けは止められない → r は実約定のまま
        out[rows[i + 1][0]] = out.get(rows[i + 1][0], 0.0) + r * 0 + r
    return out, hits, n


def portfolio(data, legs, sl_d1, method):
    p, H, Ntot = defaultdict(float), 0, 0
    for sym, dow, sgn, w in legs:
        rows, atr = data[sym]
        s, h, n = leg_returns(rows, atr, N.DOWS.index(dow), sgn, sl_d1, method)
        for d, v in s.items():
            p[d] += w * v
        H += h
        Ntot += n
    return p, (H / Ntot if Ntot else 0.0)


def calib(series, day_cap=0.04, floor_cap=0.08):
    wd, dd = min(series.values()), maxdd(series)
    m, best = 0.05, 0.0
    while m <= 6.0:
        if wd * m >= -day_cap and dd * m >= -floor_cap:
            best = m
            m = round(m + 0.05, 2)
        else:
            break
    return round(0.8 * best, 2)



def fetch_iv(ysym, rng, iv):
    """1時間足/日足を取得(寄り時刻の同定用)。"""
    import json, urllib.request, urllib.parse
    from datetime import timezone
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ysym)}?range={rng}&interval={iv}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.load(r)
    res = d["chart"]["result"][0]
    ts, q = res["timestamp"], res["indicators"]["quote"][0]
    return [(datetime.fromtimestamp(t, timezone.utc), q["open"][i])
            for i, t in enumerate(ts) if q["open"][i] is not None]


LEGS5 = [("US500", "Tue", +1, 0.333), ("HK50", "Mon", +1, 0.225),
         ("HK50", "Thu", -1, 0.225), ("JP225", "Wed", +1, 0.151),
         ("XAGUSD", "Tue", +1, 0.065)]


def final_checks(data):
    hr("[A] 最終構成の確認 — 5レッグ(XPT除外)・SL=0.5xATR_D1・X法")
    print(f"{'構成':32s} {'mult':>5s} {'窓12M':>8s} {'窓外/年':>8s} "
          f"{'窓外maxDD':>10s} {'窓外最悪日':>10s} {'フロア-8%':>9s}")
    for lab, legs, sl in (("v1.00相当 (6レッグ・SL0.5)", LEGS6, 0.5),
                          ("V案 (5レッグ・SL5.0)", LEGS5, 5.0),
                          ("v1.02 (5レッグ・SL0.5)", LEGS5, 0.5)):
        p, h = portfolio(data, legs, sl, "X")
        o = stats(p, "0000", YR); i = stats(p, YR, "9999")
        rule = calib({d: v for d, v in p.items() if d < YR})
        for m in (1.00, 0.90, 0.72):
            flag = "突破" if o['mdd'] * m <= -0.08 else "余裕"
            print(f"{(lab if m == 1.00 else ''):32s} {m:5.2f} {i['tot']*m*100:+7.1f}% "
                  f"{o['cagr']*m*100:+7.2f}% {o['mdd']*m*100:9.2f}% "
                  f"{o['worst']*m*100:9.2f}% {flag:>9s}")
        print(f"{'  → 0.8x規則が出す倍率:':32s} {rule:5.2f}   (発動率 {h*100:.1f}%)")

    hr("[B] 寄り時刻 — 日足始値と完全一致する1時間足(直近2年)")
    print(f"{'銘柄':10s} {'最頻一致UTC':>12s} {'一致日数':>10s} {'2位':>14s}")
    for sym, y in YS.items():
        try:
            d1 = {d.strftime("%Y-%m-%d"): o for d, o in fetch_iv(y, "2y", "1d")}
            h1 = fetch_iv(y, "730d", "1h")
        except Exception as e:
            print(f"{sym:10s} 取得失敗(再実行のこと): {e}")
            continue
        seen = defaultdict(set)
        for t, o in h1:
            k = t.strftime("%Y-%m-%d")
            if k in d1 and abs(o - d1[k]) < 1e-9:
                seen[t.strftime("%H:%M")].add(k)
        top = sorted(seen.items(), key=lambda x: -len(x[1]))[:2]
        if not top:
            print(f"{sym:10s} {'一致なし':>12s}")
            continue
        sec = f"{top[1][0]}({len(top[1][1])})" if len(top) > 1 else "-"
        print(f"{sym:10s} {top[0][0]:>12s} {len(top[0][1])}/{len(d1):<6d} {sec:>14s}")


def main():
    data = {}
    for sym, y in YS.items():
        rows = N.fetch_daily(y, "10y")
        data[sym] = (rows, N.atr14(rows))
        print(f"  {sym:8s} {y:8s} {len(rows)} bars  {rows[0][0]} .. {rows[-1][0]}")

    # ---------------------------------------------------- H1/H2: 接触率の比較
    hr("[1] 接触率 — 3つの判定方法 (SL距離は ATR_D1 倍数)")
    print("V=決済後の翌日安値も含む / Q=当日+ギャップも-sdで停止 / X=当日日中のみ・ギャップ実約定")
    print(f"\n{'catATR(H1換算)':>14s} {'SL/ATR_D1':>10s} {'V接触率':>8s} {'Q発動率':>8s} {'X接触率':>8s}")
    for cat, sl in ((2.5, 0.5), (5.0, 1.0), (10.0, 2.0), (25.0, 5.0)):
        row = []
        for m in ("V", "Q", "X"):
            _, h = portfolio(data, LEGS6, sl, m)
            row.append(h)
        print(f"{cat:14.1f} {sl:10.1f} {row[0]*100:7.1f}% {row[1]*100:7.1f}% {row[2]*100:7.1f}%")
    print("\n※ V列が Q/X より一貫して高ければ、決済後バーの二重計上(H1)が実在する。")

    # ---------------------------------------------------- H2/H4: 成績と校正
    for method, lab in (("Q", "Q法(ギャップも-sdで停止=楽観)"),
                        ("X", "X法(ギャップ実約定=悲観・先読み除去)")):
        hr(f"[2-{method}] {lab} — 選抜窓 vs 窓外")
        print(f"{'catATR':>8s} {'発動率':>7s} | {'窓12M':>8s} {'窓外/年':>8s} "
              f"{'窓外maxDD':>10s} {'窓外最悪日':>10s} | {'規則mult(全期間)':>15s} {'規則mult(窓外)':>14s}")
        for cat, sl in ((2.5, 0.5), (5.0, 1.0), (10.0, 2.0), (25.0, 5.0), ("なし", None)):
            p, h = portfolio(data, LEGS6, sl, method)
            i = stats(p, YR, "9999")
            o = stats(p, "0000", YR)
            full = {d: v for d, v in p.items()}
            out = {d: v for d, v in p.items() if d < YR}
            print(f"{str(cat):>8s} {h*100:6.1f}% | {i['tot']*100:+7.1f}% {o['cagr']*100:+7.2f}% "
                  f"{o['mdd']*100:9.2f}% {o['worst']*100:9.2f}% | {calib(full):15.2f} {calib(out):14.2f}")

    # ---------------------------------------------------- 退化バー (V の B-3-3)
    hr("[3] 退化バー O=H=L=C の比率 (V の XPT 除外根拠の検証)")
    print(f"{'銘柄':10s} {'系列':8s} {'全体':>8s} {'直近12M':>9s}")
    for sym, y in YS.items():
        rows = data[sym][0]
        deg = sum(1 for r in rows if r[1] == r[2] == r[3] == r[4])
        r12 = [r for r in rows if r[0] >= YR]
        d12 = sum(1 for r in r12 if r[1] == r[2] == r[3] == r[4])
        print(f"{sym:10s} {y:8s} {deg/len(rows)*100:7.1f}% {d12/max(len(r12),1)*100:8.1f}%")

    # ---------------------------------------------------- レッグ別窓外寄与
    final_checks(data)

    hr("[4] レッグ別 窓外寄与 (X法・catATR=2.5相当)")
    print(f"{'レッグ':16s} {'w':>6s} {'窓12M':>9s} {'窓外/年':>9s} {'窓外t':>7s}")
    for sym, dow, sgn, w in LEGS6:
        rows, atr = data[sym]
        s, _, _ = leg_returns(rows, atr, N.DOWS.index(dow), sgn, 0.5, "X")
        i = stats(s, YR, "9999")
        o = stats(s, "0000", YR)
        ov = [v for d, v in s.items() if d < YR]
        t = (statistics.mean(ov) / (statistics.stdev(ov) / len(ov) ** 0.5)) if len(ov) > 2 else 0
        print(f"{sym+'_'+dow+('_L' if sgn>0 else '_S'):16s} {w:6.3f} "
              f"{i['tot']*100:+8.1f}% {o['cagr']*w*100:+8.2f}% {t:7.2f}")


if __name__ == "__main__":
    main()
