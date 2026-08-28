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
FX = ["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY",
      "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF"]
IDX = ["US500","NAS100","US30","JP225","HK50","GER40","UK100"]


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
    emit(f"\n## 全20銘柄\n\n- 平均 **{st.mean(g1 + g2):+.1%}**"
         f" / 最低 {min(g1 + g2):+.1%} / 最高 {max(g1 + g2):+.1%}")
    if ev:
        dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "indicator-next", "EVIDENCE.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(HEADER + "\n---\n\n" + "\n".join(OUT) + "\n\n---\n" + FOOTER)
        print(f"\n書き出し: {os.path.normpath(dest)}")
