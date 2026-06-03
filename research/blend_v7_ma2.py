"""
blend_v7_ma2.py — 単独（v7） vs 分散（v7+MA2）の公正比較（ボラ正規化・10年月次）。

- v7 月次 = v7_weekly_returns（等加重ショット）を月次集約。
- MA2 月次 = research/ma2.py の月次TSMOM。
- 公正化: 各戦略を年率ボラ10%に正規化（サイズの恣意性を排除, docs/23の作法）。
- ブレンドは各重みで合成 → さらに年率10%に再正規化して「同一リスクでの質」を比較。
出力: 比較表 ＋ エクイティ曲線 PNG。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_io import load_v7_weekly
from ma2 import ma2_monthly

TARGET_VOL = 0.10  # 年率10%に正規化


def stats(m: pd.Series) -> dict:
    m = m.dropna()
    ann_vol = m.std() * np.sqrt(12)
    ann_ret = m.mean() * 12
    eq = (1 + m).cumprod()
    mdd = -((eq - eq.cummax()) / eq.cummax()).min()
    cagr = eq.iloc[-1] ** (12 / len(m)) - 1
    return dict(cagr=cagr, ann_ret=ann_ret, ann_vol=ann_vol,
                sharpe=ann_ret / ann_vol if ann_vol else 0.0, maxdd=mdd)


def norm(m: pd.Series, target=TARGET_VOL) -> pd.Series:
    v = m.std() * np.sqrt(12)
    return m * (target / v) if v > 0 else m


def main():
    v7 = load_v7_weekly().resample("ME").sum()
    ma2 = ma2_monthly()
    df = pd.concat([v7.rename("v7"), ma2.rename("ma2")], axis=1).dropna()
    print(f"共通月次: {len(df)} ヶ月  {df.index.min().date()}..{df.index.max().date()}")
    corr = df["v7"].corr(df["ma2"])
    print(f"v7×MA2 相関(月次, 10年) = {corr:+.3f}\n")

    v7n, ma2n = norm(df["v7"]), norm(df["ma2"])

    # 各重み（v7比率 w）でブレンド→年率10%に再正規化して同一リスク比較
    print(f"{'配分(v7:MA2)':>14} {'Sharpe':>7} {'CAGR':>8} {'maxDD':>7}  (全て年率vol10%に正規化)")
    weights = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.0]
    rows = {}
    for w in weights:
        blend = w * v7n + (1 - w) * ma2n
        bn = norm(blend)
        s = stats(bn)
        rows[w] = bn
        label = f"{int(w*100)}:{int((1-w)*100)}"
        star = "  ← v7単独" if w == 1.0 else ("  ← MA2単独" if w == 0.0 else "")
        print(f"{label:>14} {s['sharpe']:7.2f} {100*s['cagr']:7.1f}% {100*s['maxdd']:6.1f}%{star}")

    # 生（非正規化）の単独比較も併記
    print("\n--- 参考: 生（非正規化）の単独 ---")
    for name, m in [("v7", df['v7']), ("MA2", df['ma2'])]:
        s = stats(m)
        print(f"  {name:4s}: Sharpe {s['sharpe']:.2f}  年率 {100*s['ann_ret']:+.1f}%  "
              f"vol {100*s['ann_vol']:.1f}%  maxDD {100*s['maxdd']:.1f}%")

    # --- エクイティ曲線 PNG（年率10%正規化）---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 6))
        for w, lab, style in [(1.0, "v7 単独 (100:0)", "-"),
                              (0.7, "分散 v7:MA2 = 70:30", "-"),
                              (0.0, "MA2 単独 (0:100)", "--")]:
            eq = (1 + rows[w]).cumprod()
            ax.plot(eq.index, eq.values, style, label=lab, linewidth=2)
        ax.set_title("単独 vs 分散（年率ボラ10%正規化・10年月次）")
        ax.set_ylabel("累積エクイティ（初期=1.0）"); ax.legend(); ax.grid(alpha=0.3)
        out = "reports/blend_v7_ma2.png"
        fig.tight_layout(); fig.savefig(out, dpi=110)
        print(f"\n[WROTE] {out}")
    except Exception as e:
        print("chart skip:", e)


if __name__ == "__main__":
    main()
