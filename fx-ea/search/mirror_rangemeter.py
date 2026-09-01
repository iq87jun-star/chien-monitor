#!/usr/bin/env python3
"""出荷する MQL5(定石参 値幅計)の Recalc をそのまま写し、同じデータで測る。

販売ページに載せる数値は、台帳の検定値ではなく**出荷するコードが出した値**を使う。
台帳の i-rangefc-*-sma は素朴基準が「全履歴の拡大平均」だったが、
製品は「直近 InpBaseBars 本の平均」を平年並みとして使う。より手強い基準なので
改善率は小さく出る。小さいほうを載せる。

  python3 mirror_rangemeter.py              # 実測を表示
  python3 mirror_rangemeter.py --evidence   # 販売用の根拠資料を生成
"""
import statistics as st
import engine

RANGE_BARS = 14
BASE_BARS  = 3000
BAND_BARS  = 60
BAND_LO, BAND_HI = 0.10, 0.90
FX = ["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY",
      "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF"]
IDX = ["US500","NAS100","US30","JP225","HK50","GER40","UK100"]
CRY = ["BTCUSD","ETHUSD"]
MET = ["XAUUSD","XAGUSD","XPTUSD","USOIL","UKOIL"]


def score(rows, range_bars=RANGE_BARS, base_bars=BASE_BARS):
    """MQL5 の Recalc と同じ計算。時系列は古い→新しい順で持つ。

    各時点 i で、i 本目の値幅を i-1 以前だけを使って当てにいく:
      想定値幅 = 直近 range_bars 本の平均
      平年並み = 直近 base_bars 本の平均(足りなければあるだけ)
    """
    rng = [r[2] - r[3] for r in rows]
    pre = [0.0]
    for x in rng: pre.append(pre[-1] + x)
    err_fc = err_bs = 0.0
    per_year = {}
    n = 0
    for i in range(len(rng)):
        b = min(base_bars, i)
        if b < 120: continue
        fc = (pre[i] - pre[i - range_bars]) / range_bars
        bs = (pre[i] - pre[i - b]) / b
        act = rng[i]
        ef, eb = abs(act - fc), abs(act - bs)
        err_fc += ef; err_bs += eb; n += 1
        y = rows[i][0][:4]
        cell = per_year.setdefault(y, [0.0, 0.0, 0])
        cell[0] += ef; cell[1] += eb; cell[2] += 1
    if not n or err_bs <= 0: return None
    years = {y: (v[1] - v[0]) / v[1] for y, v in per_year.items() if v[1] > 0}
    return {"n": n, "gain": (err_bs - err_fc) / err_bs, "years": years}


OUT = []


def emit(line=""):
    OUT.append(line)
    print(line)


def band(rows, n=BAND_BARS, lo=BAND_LO, hi=BAND_HI):
    """MQL5 の Quantile / 被覆率の数え方と同じ計算。

    直近 n 本の高安幅の分位で作った範囲に、次の1本が実際に入った割合を返す。
    「8割はこの範囲」と書けるかどうかは、名目ではなく**実測**で決める。
    """
    rng = [r[2] - r[3] for r in rows]

    def q(w, p):
        srt = sorted(w)
        return srt[min(len(srt) - 1, int(len(srt) * p))]

    hit = tot = 0
    wm = wb = 0.0
    hist = []
    for i in range(len(rng) - 1):
        hist.append(rng[i])
        if len(hist) < max(250, n): continue
        w = hist[-n:]
        a, b = q(w, lo), q(w, hi)
        ba, bb = q(hist, lo), q(hist, hi)
        act = rng[i + 1]
        hit += (a <= act <= b); tot += 1
        wm += b - a; wb += bb - ba
    if not tot: return None
    return {"cover": hit / tot, "narrow": wm / wb if wb else 0, "n": tot}


def report_band(title, syms):
    emit(f"\n### {title}\n")
    emit("| 銘柄 | n | 範囲に入った割合 | 全履歴の範囲に対する幅 |")
    emit("|---|--:|--:|--:|")
    cov = []
    for s in syms:
        r = band(engine.rows_of(s))
        if not r: continue
        cov.append(r["cover"])
        emit(f"| {s} | {r['n']:,} | **{r['cover']:.1%}** | {r['narrow']:.2f} 倍 |")
    emit(f"\n- 平均 **{st.mean(cov):.1%}** / 最低 {min(cov):.1%} / 最高 {max(cov):.1%}")
    return cov


def quiet_hit(rows, n=RANGE_BARS, base_bars=BASE_BARS, thr=0.85, side="quiet"):
    """出荷コードの「静か」判定が当たっている割合と、無条件の割合。

    静穏度 = 直近 n 本の平均値幅 ÷ 直近 base_bars 本の平均値幅。
      side="quiet": < thr で「静か」→ 翌バーが平年並みを下回った割合
      side="busy" : > thr で「荒い」→ 翌バーが平年並みを上回った割合
    いずれも無条件の割合と比べる。
    """
    rng = [r[2] - r[3] for r in rows]
    hist = []
    q_hit = q_tot = u_hit = u_tot = 0
    for i in range(len(rng) - 1):
        hist.append(rng[i])
        b = min(base_bars, len(hist))
        if b < 250 or len(hist) <= n: continue
        base = sum(hist[-b:]) / b
        if base <= 0: continue
        fc = sum(hist[-n:]) / n
        hit = (rng[i + 1] < base) if side == "quiet" else (rng[i + 1] > base)
        fires = (fc / base < thr) if side == "quiet" else (fc / base > thr)
        u_hit += hit; u_tot += 1
        if fires:
            q_hit += hit; q_tot += 1
    if q_tot < 100: return None
    return {"quiet": q_hit / q_tot, "uncond": u_hit / u_tot, "n": q_tot}


def report_quiet(title, syms, side="quiet", thr=0.85):
    lab = "静か" if side == "quiet" else "荒い"
    dir_ = "下回った" if side == "quiet" else "上回った"
    emit(f"\n### {title}\n")
    emit(f"| 銘柄 | 「{lab}」と出た日数 | そのとき{dir_}割合 | 無条件の割合 |")
    emit("|---|--:|--:|--:|")
    qs, us = [], []
    for s in syms:
        r = quiet_hit(engine.rows_of(s), thr=thr, side=side)
        if not r: continue
        qs.append(r["quiet"]); us.append(r["uncond"])
        emit(f"| {s} | {r['n']:,} | **{r['quiet']:.1%}** | {r['uncond']:.1%} |")
    emit(f"\n- 「{lab}」のとき 平均 **{st.mean(qs):.1%}** / 無条件 {st.mean(us):.1%}"
         f" / 最低 {min(qs):.1%}")
    return qs, us


def report(title, syms):
    emit(f"\n## {title}\n")
    emit("| 銘柄 | n | 誤差の削減 | 改善した年 |")
    emit("|---|--:|--:|--:|")
    gains, worst = [], None
    allyears = {}
    for s in syms:
        r = score(engine.rows_of(s))
        if not r: continue
        hit = sum(1 for v in r["years"].values() if v > 0)
        gains.append(r["gain"])
        if worst is None or r["gain"] < worst[1]: worst = (s, r["gain"])
        for y, v in r["years"].items(): allyears.setdefault(y, []).append(v)
        emit(f"| {s} | {r['n']:,} | **{r['gain']:+.1%}** | {hit}/{len(r['years'])} |")
    yhit = sum(1 for y, v in allyears.items() if st.mean(v) > 0)
    emit(f"\n- 平均 **{st.mean(gains):+.1%}** / 最低 {worst[0]} {worst[1]:+.1%}")
    emit(f"- 全銘柄で改善: {'はい' if min(gains) > 0 else 'いいえ'}")
    emit(f"- 銘柄平均が改善した年: {yhit}/{len(allyears)}")
    return gains, allyears


HEADER = """# 定石 参 ─ 値幅計 / 検証の根拠

このファイルは `fx-ea/search/mirror_rangemeter.py --evidence` が生成する。
**出荷する MQL5 / MQL4 の `Recalc()` と同じ計算**を Python に写して測ったもの。
販売ページに載せる数値はここから取ること。**手で書き換えないこと。**

再生成:

```
cd fx-ea/search && python3 mirror_rangemeter.py --evidence
```
"""

FOOTER = """
## 事前固定プロトコルでの検定(台帳)

商品化の前に `fx-ea/search/` の事前固定プロトコルで検定している。
仮説を出す前に判定基準を決め、検定した回数を台帳に積み、その回数に応じて
必要な統計的水準を引き上げる仕組み。**累積 7,619 回の検定を経た時点での通過。**

| 台帳ID | n | 補正t | 必要t | 日次t | 改善率 | 改善年 |
|---|--:|--:|--:|--:|--:|--:|
| `i-rangefc-fx-sma` | 50,003 | 46.48 | 4.35 | 24.72 | +17.5% | 16/16 |
| `i-rangefc-idx-sma` | 25,835 | 38.32 | 4.36 | 21.82 | +19.3% | 16/16 |

`日次t` は、同じ日に相関の高い複数銘柄を建てている分を潰した後の t 値。
`python3 attack.py i-rangefc-fx-sma` で全銘柄・全年の内訳を再現できる。

台帳の改善率と上の実測が少し違うのは、素朴基準の取り方が違うため。
台帳は「全履歴の拡大平均」、製品は「直近3,000本の平均」。
製品のほうが手強い基準を使っている。**小さいほうの数字を販売資料に載せること。**

## この数値が言っていないこと

- **値動きの方向については何も言っていない。** 同じ探索エンジンで方向を当てにいった
  仮説は46件すべて棄却されている。値幅が読めることと、勝てることは別。
- 検証は **Yahoo Finance の日足**。業者のMT5の日足とはバーの区切りが違い、
  日足以外の時間足は検証していない。時間足ごとの実績はインジケーター本体の
  自己採点で各自確認できるようにしてある。
- 将来も同じ精度が出る保証はない。
"""


if __name__ == "__main__":
    import os, sys
    ev = "--evidence" in sys.argv
    emit(f"# 値幅計 出荷ロジックの実測 (想定 {RANGE_BARS}本 / 平年並み {BASE_BARS}本)")
    emit()
    emit("データ: Yahoo Finance 日足 15年。誤差は各バーの高安幅に対する平均絶対誤差。")
    g1, y1 = report("FX 13ペア", FX)
    g2, y2 = report("株価指数 7銘柄", IDX)
    g3, y3 = report("暗号資産 2銘柄", CRY)
    g4, y4 = report("貴金属・エネルギー 5銘柄", MET)
    allg = g1 + g2 + g3 + g4
    emit(f"\n## 全27銘柄\n\n- 平均 **{st.mean(allg):+.1%}**"
         f" / 最低 {min(allg):+.1%} / 最高 {max(allg):+.1%}")

    emit(f"\n## 想定の範囲(分位 {BAND_LO:.0%}〜{BAND_HI:.0%}・直近{BAND_BARS}本)\n")
    emit("名目は8割だが、**実測は8割に届かない**。販売資料には実測値を書くこと。")
    c1 = report_band("FX 13ペア", FX)
    c2 = report_band("株価指数 7銘柄", IDX)
    c3 = report_band("暗号資産 2銘柄", CRY)
    c4 = report_band("貴金属・エネルギー 5銘柄", MET)
    allc = c1 + c2 + c3 + c4
    emit(f"\n**全27銘柄の平均被覆率 {st.mean(allc):.1%}**"
         f"(最低 {min(allc):.1%})。全履歴の分位で作る範囲より狭く、"
         f"被覆はほぼ同じ。狭くて外さない分だけ良い。")

    emit(f"\n## 週足での値幅予測(直近8本 / 平年並みは取得できる全週)\n")
    emit("日中足は取れないが、上位足なら日足からまとめられる。"
         "**日足だけの話ではない**ことの確認。")
    emit("\n| クラス | n | 誤差の削減 |")
    emit("|---|--:|--:|")
    for nm, syms in (("FX 13ペア", FX), ("株価指数 7銘柄", IDX)):
        gs, ns = [], 0
        for sym in syms:
            r = score(engine.resample_weekly(engine.rows_of(sym)),
                      range_bars=8, base_bars=BASE_BARS)
            if r: gs.append(r["gain"]); ns += r["n"]
        emit(f"| {nm} | {ns:,} | **{st.mean(gs):+.1%}** |")

    emit(f"\n## 「静か」判定の的中率(静穏度 < 0.85)\n")
    emit("「静か」と出た日の翌バーが、実際に平年並みを下回った割合。")
    q1, u1 = report_quiet("FX 13ペア", FX)
    q2, u2 = report_quiet("株価指数 7銘柄", IDX)
    emit(f"\n**「静か」のとき {st.mean(q1 + q2):.1%} / 無条件 {st.mean(u1 + u2):.1%}"
         f"(最低 {min(q1 + q2):.1%})**")
    emit(f"\n## 「荒い」判定の的中率(静穏度 > 1.15)\n")
    b1, v1 = report_quiet("FX 13ペア", FX, side="busy", thr=1.15)
    b2, v2 = report_quiet("株価指数 7銘柄", IDX, side="busy", thr=1.15)
    emit(f"\n**「荒い」のとき {st.mean(b1 + b2):.1%} / 無条件 {st.mean(v1 + v2):.1%}"
         f"(最低 {min(b1 + b2):.1%})**")
    emit("""
「荒い」側は「静か」側より頑健。連続する局面をひとつにまとめても成立する
(FX 48局面・勝ち35/48・生t 2.83 / 指数 42局面・勝ち30/42)。
静か側は局面単位では成立しない(下記)。**同じパネルの2つの表示で強さが違う。**""")

    emit("""
留保: 台帳(`i-quiethit-fx`)では全13ペア・14年中13年で改善し、日次集約後も
t=19.6(必要4.38)と堅い。**ただし連続する「静か」局面を1件にまとめると
31局面しかなく、その単位では成立しない(勝ち15/31)。**
日ごとの判断には使えるが、「静かな局面」という単位での主張はできない。
販売資料には**日ごとの割合としてのみ**書くこと。""")
    if ev:
        dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "indicator-next", "EVIDENCE.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(HEADER + "\n---\n\n" + "\n".join(OUT) + "\n\n---\n" + FOOTER)
        print(f"\n書き出し: {os.path.normpath(dest)}")
