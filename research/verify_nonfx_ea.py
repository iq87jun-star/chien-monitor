#!/usr/bin/env python3
"""FN100k #14074882 RecentFit NonFX2 の EA設定検証 (2026-08-15).

research/nonfx_screen.py が選抜した6セルに対し、EA側の**執行設定**が
研究セルを再現できているかを検証する。結果は research/nonfx_ea_review.md。

検証項目:
  1. 各銘柄の現物寄り時刻(=研究o2oの起点)を日足始値と1時間足始値の
     完全一致照合で同定 → EAの InpDowHoursUTC が正しいかを判定
  2. 建て時刻ずれの感応度(研究o2o / 1セッション先送り / 丸1日ずれ)
  3. 災害SL(InpCatastropheATR)の発動率と損益・DDへの影響
     ※建玉は翌日"寄り"で決済されるため、日中逆行は**当日のみ**。
       翌日の安値まで含めると発動率もDDも過大評価になる(初版の誤り)
  4. 倍率校正: nonfx_screen.py の規則(最悪日≥-4%かつDD≥-8%の最大倍率×0.8)を
     SLなし系列と実稼働系列(SL込み)の双方に適用
  5. 1ショット想定元本 vs 最小ロット(0.01)

実行: python3 research/verify_nonfx_ea.py
"""
import json, sys, urllib.request
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, __import__("os").path.dirname(__file__))
from nonfx_screen import fetch_daily, atr14, window_stats, UA

# (レッグ名, Yahooシンボル, 曜日, 方向, 重み, v1.01の建て時刻UTC)
LEGS = [
    ("US500_Tue_L",  "^GSPC", "Tue", +1, 0.309, [14, 15, 16, 17]),
    ("HK50_Mon_L",   "^HSI",  "Mon", +1, 0.209, [2, 3]),
    ("HK50_Thu_S",   "^HSI",  "Thu", -1, 0.209, [2, 3]),
    ("JP225_Wed_L",  "^N225", "Wed", +1, 0.140, [0, 1, 2, 3]),
    ("XPTUSD_Tue_L", "PL=F",  "Tue", +1, 0.072, [4, 5]),
    ("XAGUSD_Tue_L", "SI=F",  "Tue", +1, 0.060, [4]),
]
DOWS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YR_AGO = datetime.now(timezone.utc).replace(
    year=datetime.now(timezone.utc).year - 1).strftime("%Y-%m-%d")
DATA = {y: (fetch_daily(y), atr14(fetch_daily(y))) for _, y, _, _, _, _ in LEGS}


def maxdd(series, lo=None):
    eq = peak = m = 0.0
    for d in sorted(series):
        if lo and d < lo:
            continue
        eq += series[d]; peak = max(peak, eq); m = min(m, eq - peak)
    return m


# --------------------------------------------------------- 1. 寄り時刻の同定
def identify_open_hours():
    print("=== 1. 現物寄り時刻の同定(日足始値と完全一致する1時間足バー) ===")
    for sym, name in [("%5EGSPC", "US500"), ("%5EHSI", "HK50"), ("%5EN225", "JP225"),
                      ("PL%3DF", "XPTUSD"), ("SI%3DF", "XAGUSD")]:
        def get(iv):
            u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                 f"?range=1mo&interval={iv}")
            r = urllib.request.Request(u, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(r, timeout=60).read().decode()
                              )["chart"]["result"][0]
        try:
            dd_, hh = get("1d"), get("1h")
        except Exception as e:
            print(f"  {name:8s} 取得失敗 {e}"); continue
        dop = [o for o in dd_["indicators"]["quote"][0]["open"] if o]
        hb = [(datetime.fromtimestamp(t, tz=timezone.utc), o) for t, o in
              zip(hh["timestamp"], hh["indicators"]["quote"][0]["open"]) if o]
        c, miss = Counter(), 0
        for o in dop:
            m = [t for t, p in hb if abs(p - o) < 1e-9]
            if m: c[min(m).strftime("%H:%M")] += 1
            else: miss += 1
        top = c.most_common(2)
        verdict = "確定" if top and top[0][1] >= len(dop) * 0.8 else "★一致取れず(集計規約が異なる)"
        print(f"  {name:8s} {dict(top)} 不一致{miss}日 → {verdict}")


# ------------------------------------------------- 2. 建て時刻ずれの感応度
def series_for(rows, di, sgn, mode):
    out = {}
    for i in range(len(rows) - 2):
        if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di:
            continue
        if   mode == "o2o":  a, b, k = rows[i][1],   rows[i + 1][1], rows[i + 1][0]
        elif mode == "c2c":  a, b, k = rows[i][4],   rows[i + 1][4], rows[i + 1][0]
        else:                a, b, k = rows[i + 1][1], rows[i + 2][1], rows[i + 2][0]
        out[k] = sgn * (b - a) / a
    return out


def timing_sensitivity():
    print("\n=== 2. 建て時刻ずれの感応度 ===")
    print(f"{'窓':22s} {'12M合成':>9s} {'全期間':>9s} {'maxDD(12M)':>11s}")
    for mode, lab in (("o2o", "研究o2o(正)"), ("c2c", "1セッション先送り"), ("nxt", "丸1日ずれ")):
        port = {}
        for name, y, dw, sgn, w, _ in LEGS:
            s = series_for(DATA[y][0], DOWS.index(dw), sgn, mode)
            for d, v in s.items():
                port[d] = port.get(d, 0.0) + w * v
        p12 = {d: v for d, v in port.items() if d >= YR_AGO}
        print(f"  {lab:20s} {window_stats(p12, YR_AGO, TODAY)['tot']*100:+8.1f}% "
              f"{window_stats(port,'0000',TODAY)['tot']*100:+8.1f}% {maxdd(port, YR_AGO)*100:10.2f}%")
    print("  レッグ別(研究o2o → 丸1日ずれ):")
    for name, y, dw, sgn, w, _ in LEGS:
        a = series_for(DATA[y][0], DOWS.index(dw), sgn, "o2o")
        b = series_for(DATA[y][0], DOWS.index(dw), sgn, "nxt")
        print(f"    {name:14s} {window_stats(a,YR_AGO,TODAY)['tot']*100:+7.1f}% → "
              f"{window_stats(b,YR_AGO,TODAY)['tot']*100:+7.1f}%")


# ------------------------------------------- 3&4. 災害SLの影響と倍率校正
def build_port(sl_atr_d1):
    """sl_atr_d1: SL距離をATR_D1倍で指定(None=SLなし)。
    建玉は当日寄り→翌日寄り。日中逆行は当日のみ(翌日は寄りで決済)。"""
    port, hits, n = {}, 0, 0
    for name, y, dw, sgn, w, _ in LEGS:
        rows, at = DATA[y]; di = DOWS.index(dw)
        for i in range(len(rows) - 1):
            if datetime.strptime(rows[i][0], "%Y-%m-%d").weekday() != di: continue
            if at[i] is None or at[i] <= 0: continue
            e = rows[i][1]; r = sgn * (rows[i + 1][1] - e) / e; n += 1
            if sl_atr_d1:
                sd = sl_atr_d1 * at[i]
                adv = rows[i][3] if sgn > 0 else rows[i][2]
                if ((e - adv) >= sd if sgn > 0 else (adv - e) >= sd) or r < -sd / e:
                    r = -sd / e; hits += 1
            port[rows[i + 1][0]] = port.get(rows[i + 1][0], 0.0) + w * r
    return port, (hits / n if n else 0.0)


def calibrate(series, day_cap=0.04, floor_cap=0.08):
    """nonfx_screen.py:calibrate と同一規則。最大倍率×0.8。"""
    wd, dd_ = min(series.values()), maxdd(series)
    m, best = 0.05, 0.0
    while m <= 6.0:
        if wd * m >= -day_cap and dd_ * m >= -floor_cap:
            best = m; m = round(m + 0.05, 2)
        else:
            break
    return round(0.8 * best, 2), wd, dd_


def sl_and_mult():
    print("\n=== 3&4. 災害SL(InpCatastropheATR)と倍率校正 ===")
    print("  ATR(H1,24)≈ATR_D1/5 と仮定。Σw=1.0 / mult=1.0 基準")
    print(f"{'catATR':>8s} {'発動率':>7s} {'12M':>8s} {'全期間':>9s} {'最悪日':>8s} {'maxDD':>8s} {'規則mult':>9s}")
    for lab, sl in ((2.5, 0.5), (5.0, 1.0), (7.5, 1.5), (10.0, 2.0), (12.5, 2.5), ("なし", None)):
        p, h = build_port(sl)
        p12 = {d: v for d, v in p.items() if d >= YR_AGO}
        mult, wd, dd_ = calibrate(p)
        print(f"{str(lab):>8s} {h*100:6.1f}% {window_stats(p12,YR_AGO,TODAY)['tot']*100:+7.1f}% "
              f"{window_stats(p,'0000',TODAY)['tot']*100:+8.1f}% {wd*100:7.2f}% {dd_*100:7.2f}% {mult:8.2f}")
    p, _ = build_port(0.5)
    mult, wd, dd_ = calibrate(p)
    print(f"\n  EA v1.01既定 (catATR=2.5 / mult=1.0):")
    print(f"    全期間 最悪日{wd*100:.2f}% / maxDD{dd_*100:.2f}% "
          f"→ フロア-8%まで{8.0-abs(dd_*100):.2f}pt / 失格線-10%まで{10.0-abs(dd_*100):.2f}pt")
    print(f"    規則上限 mult={mult}(引き上げは正式再校正後に限る)")


# ------------------------------------------------- 5. 最小ロット制約
def lot_check():
    print("\n=== 5. 1ショット想定元本 vs 最小ロット(0.01) ===")
    px = {n: DATA[y][0][-1][4] for n, y, _, _, _, _ in
          [(l[0].split("_")[0], l[1], 0, 0, 0, 0) for l in LEGS]}
    usdjpy = fetch_daily("JPY=X")[-1][4]
    per_lot = {  # 1ロットの想定元本(USD)。指数の契約サイズはブローカー依存
        "US500": px["US500"] * 1, "HK50": px["HK50"] * 10 / 7.80,
        "JP225": px["JP225"] * 100 / usdjpy,
        "XPTUSD": px["XPTUSD"] * 100, "XAGUSD": px["XAGUSD"] * 5000,
    }
    for mult in (0.68, 1.00):
        print(f"  -- InpMult={mult} / 基準残高100,000 --")
        for name, _, _, _, w, hrs in LEGS:
            sym = name.split("_")[0]
            for nh, tag in ((4, "v1.00(4分割)"), (len(hrs), f"v1.01({len(hrs)}分割)")):
                notional = 100000 * w * mult / nh
                lots = notional / per_lot[sym]
                got = (int(lots / 0.01) * 0.01) * per_lot[sym]
                flag = ("★0.01未満=発注されず" if lots < 0.01
                        else f"実効{got/notional*100:.0f}%" if got < notional * 0.9 else "OK")
                print(f"    {sym:7s} {tag:14s} ${notional:7.0f} / 1lot ${per_lot[sym]:8.0f} "
                      f"= {lots:7.4f}lot  {flag}")
        print()


if __name__ == "__main__":
    identify_open_hours()
    timing_sensitivity()
    sl_and_mult()
    lot_check()
    print("注: 契約サイズ・digits はブローカー依存。EA起動時の [SPEC]/[PREFLIGHT] ログで実測すること。")
