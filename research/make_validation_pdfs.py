#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2本の検証結果PDFを生成する（v7確度 / 2本目=多資産トレンド+探索済み）。
出力: reports/v7_10year_validation.pdf, reports/edge2_multiasset_and_search_log.pdf
データ出典: docs/18, docs/23, docs/24, docs/14/17/20/21/22（10年実測の確定値）。
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# 日本語フォント
import matplotlib.font_manager as fm
for cand in ["IPAGothic", "IPAPGothic"]:
    try:
        fm.findfont(cand, fallback_to_default=False)
        plt.rcParams["font.family"] = cand
        break
    except Exception:
        pass
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(__file__), "..", "reports")
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)

FOOT = "出典: 10年実測(Dukascopy H1 FX / Yahoo日足 多資産) docs/18,23,24。シミュレーション・将来を保証しない。"

def text_page(pdf, title, lines, foot=FOOT, fs=11):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    fig.subplots_adjust(left=0.07, right=0.96, top=0.93, bottom=0.06)
    ax = fig.add_subplot(111); ax.axis("off")
    ax.text(0, 1.0, title, fontsize=16, fontweight="bold", va="top")
    y = 0.95
    for ln in lines:
        size = fs
        if ln.startswith("##"):
            ln = ln[2:].strip(); size = fs + 2; y -= 0.005
            ax.text(0, y, ln, fontsize=size, fontweight="bold", va="top")
        else:
            ax.text(0, y, ln, fontsize=size, va="top")
        y -= 0.028 if not ln.startswith("##") else 0.034
    ax.text(0, -0.02, foot, fontsize=7, color="gray", va="top")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    pdf.savefig(fig); plt.close(fig)

def table_page(pdf, title, col_labels, rows, note="", col_w=None, hl=None):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.subplots_adjust(left=0.06, right=0.97, top=0.92, bottom=0.07)
    ax = fig.add_subplot(111); ax.axis("off")
    ax.text(0, 1.0, title, fontsize=15, fontweight="bold", va="top", transform=ax.transAxes)
    tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.6)
    for j in range(len(col_labels)):
        c = tbl[0, j]; c.set_facecolor("#2c3e50"); c.set_text_props(color="white", fontweight="bold")
    if col_w:
        for j, w in enumerate(col_w):
            for i in range(len(rows) + 1):
                tbl[i, j].set_width(w)
    if hl:
        for ri in hl:
            for j in range(len(col_labels)):
                tbl[ri, j].set_facecolor("#fdf2d0")
    if note:
        ax.text(0, 0.02, note, fontsize=8, color="#444", va="bottom", transform=ax.transAxes, wrap=True)
    ax.text(0, -0.04, FOOT, fontsize=7, color="gray", va="top", transform=ax.transAxes)
    pdf.savefig(fig); plt.close(fig)

def bar_page(pdf, title, labels, values, ylabel, note="", colors=None):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.subplots_adjust(left=0.12, right=0.94, top=0.9, bottom=0.45)
    ax = fig.add_subplot(111)
    ax.text(0, 1.12, title, fontsize=15, fontweight="bold", va="top", transform=ax.transAxes)
    bars = ax.bar(labels, values, color=colors or "#2980b9")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel(ylabel)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + (1 if v >= 0 else -3),
                f"{v:+.1f}", ha="center", fontsize=9)
    if note:
        fig.text(0.07, 0.30, note, fontsize=9, va="top")
    fig.text(0.07, 0.03, FOOT, fontsize=7, color="gray")
    pdf.savefig(fig); plt.close(fig)

# ============================================================
# PDF 1: v7 10年確度検証
# ============================================================
p1 = os.path.join(OUT, "v7_10year_validation.pdf")
with PdfPages(p1) as pdf:
    text_page(pdf, "検証結果① v7（円・月曜シーズナリティ）10年確度", [
        "対象: FundedNext Stellar / Blueberry Instant で運用中の唯一の検証済みエッジ",
        "戦略: EURJPY / GBPJPY / USDJPY を月曜 04/06/08/10 UTC に LONG、24h時間決済。",
        "      1現象(円の週明けドリフト)を3ペア×4時刻=週12ショットに分散(リスク予算配分)。",
        "データ: 実10年 H1 (2016-01〜2025-12, Dukascopy, 実bid/ask・spread)。",
        "",
        "## 一行結論",
        "v7は10年で確度が高い。週次予算0.6%なら 純益+28.6% / 最大DD6.13%(−10%枠内) /",
        "Phase1合格62.6%(中央20.0ヶ月)。月曜特異性は他曜日全敗で決定的(過剰最適化でない)。",
        "",
        "## 重要な訂正履歴（誠実な記録）",
        "初期の2.8年検証では最大DDを−4.9%と過小評価していた。ユーザー提供の10年検証で",
        "真の最大DDは予算1.5%時 約14.8%（年次最悪10.5%）と判明＝約3倍。",
        "→ エッジは本物だが、最大DDは週次予算にほぼ線形。器に収めるには予算管理が必須。",
        "",
        "## 予算と最大DDの関係（10年アンカーからの外挿）",
        " 週次0.60% → 全期間maxDD ~5.9% / 年次最悪 ~4.2%（−10%に4%マージン）✅",
        " 週次1.50% → 全期間maxDD ~14.8% / 年次最悪 ~10.5%（−10%枠を超過）⚠",
        " 週次2.50% → 全期間maxDD ~24%（非常に攻撃的）⚠",
        "現運用: 現行プロップ2.5倍=週次2.5% / インスタント1.5倍=週次1.5%（DDリスク承知の上）。",
    ])

    table_page(pdf, "v7 ウォークフォワード（10年を5分割・予算0.6%）",
        ["期間", "純益%", "最大DD%", "P1合格%", "P1中央月"],
        [["2016-01..2018-01", "−2.6", "5.37", "6.4", "18.6 ×"],
         ["2018-01..2020-01", "+4.8", "4.44", "53.1", "20.3 ✓"],
         ["2020-01..2022-01", "+9.7", "3.41", "90.0", "15.7 ✓"],
         ["2022-01..2024-01", "+11.1", "2.57", "96.0", "15.7 ✓"],
         ["2024-01..2025-12", "+5.6", "2.20", "64.5", "21.2 ✓"]],
        note="黒字 4/5。最古2016-18期のみ赤字（直近8年は全黒字）。各DDは−10%枠内。",
        hl=[3, 4])

    bar_page(pdf, "曜日プラセボ（10年・予算0.6%）純益%",
        ["月", "火", "水", "木", "金"], [28.6, -7.4, -6.2, -14.7, -61.8],
        "純益 %",
        note="月曜だけが黒字(+28.6%)。火〜金は全て赤字、金曜は−61.8%(DD63%)で壊滅。\n"
             "→ v7の月曜特異性は10年で決定的に確認。過剰最適化ではない最強の証拠。",
        colors=["#27ae60", "#c0392b", "#c0392b", "#c0392b", "#c0392b"])

    table_page(pdf, "v7 パラメータ頑健性（10年・全て黒字維持）",
        ["摂動", "純益レンジ", "判定"],
        [["入口時刻 4変種", "+20.2 〜 +33.9%", "✓ 基準依存でない"],
         ["ATR係数 {2.0,2.5,3.0}", "+24.7 〜 +32.6%", "✓ SL幅に過敏でない"],
         ["ペア各1除外", "+17.2 〜 +21.8%", "✓ 単一ペア牽引でない"],
         ["全期間(基準0.6%)", "+28.6% / maxDD6.13%", "✓ Phase1合格62.6%"]],
        note="時刻・ATR・ペアの摂動すべてで黒字維持＝過剰最適化の兆候なし。",
        col_w=[0.32, 0.40, 0.28])

    table_page(pdf, "1年あたり失格率 × ドローダウン枠（業者別の相性）",
        ["週次予算", "−10%枠 (FN/FTMO/Blueberry)", "−5%枠 (FundingPips等)"],
        [["0.6%", "0.0%", "3.0%"],
         ["1.0%", "1.1%", "23.9%"],
         ["1.5%", "9.1%", "58.5%"],
         ["2.5%", "37.9%", "92.0%"]],
        note="v7は月曜に益が集中する一日エッジ。−10%枠＆一貫性ルール無しの業者(FundedNext"
             " Stellar)が最適。−5%トレーリング＋15%一貫性ルールの業者はv7と不適合。",
        col_w=[0.22, 0.40, 0.38], hl=[3])

p1_size = os.path.getsize(p1)

# ============================================================
# PDF 2: 2本目(多資産トレンド)検証 + 探索済みログ
# ============================================================
p2 = os.path.join(OUT, "edge2_multiasset_and_search_log.pdf")
with PdfPages(p2) as pdf:
    text_page(pdf, "検証結果② 2本目探索（多資産トレンド）＋探索済みログ", [
        "目的: v7と独立な2本目エッジを厳格ハーネスで探索した全記録。",
        "規律: 事前登録(試行数N固定)・Bonferroni補正・順列検定(自己相関頑健版)・",
        "      ジャックナイフ・曜日プラセボ・v7相関ゲート・コスト計上。10年実データで選別。",
        "",
        "## 一行結論",
        "クリーンな採用(ADOPT)は無い。本資金の2本目はまだ無く、v7が唯一の検証済みエッジ。",
        "ただし多資産トレンド(金+株価指数)はFX内候補と質が違う『LEAD(有望候補)』。",
        "最有力=MA2(金+指数TSMOM): v7と10年相関−0.16(分散先)・OOSで減衰なし。",
        "→ 次の一手は『MA2をデモ前進検証で小さく追検』。3本目・4本目は未踏領域の新規探索。",
        "",
        "## なぜ多資産トレンドだけ前進したか",
        "FX内の順方向・カレンダー・平均回帰・時系列モメンタムは全滅(下記ログ)。",
        "文献の教訓=時系列モメンタムは『複数資産クラスの分散バスケット』でこそ機能する。",
        "唯一の未トライ土俵=金・株価指数・暗号の多資産トレンドだけが正の兆候を示した。",
    ])

    table_page(pdf, "多資産トレンド edge5（10年・頑健版・採用ゼロ）",
        ["候補", "純益", "maxDD", "頑健p", "v7相関", "grade"],
        [["MA1 6資産TSMOM", "+127%", "−49.8%", "0.077", "−0.10", "LEAD 4/6"],
         ["MA2 金+指数TSMOM", "+52.3%", "−19.9%", "0.085", "−0.16", "LEAD 4/6"],
         ["MA3 暗号のみ", "+25.0%", "−93.6%", "0.134", "−0.07", "REJECT"],
         ["MA4 横断XSMOM", "−45.9%", "−88.6%", "0.244", "−0.02", "REJECT"],
         ["MA5 Donchian55", "+1724%", "−78.1%", "0.023", "+0.08", "LEAD 5/6"],
         ["MA6 +FX8横断", "+31.4%", "−33.2%", "0.20", "−0.09", "REJECT"]],
        note="ADOPT: なし / LEAD: MA1,MA2,MA5。全候補 maxDD −20〜−94% で−10%口座と非両立。"
             "採るなら大幅縮小サイズの衛星＋デモ前進検証が前提。本資金即投入は不可。",
        col_w=[0.26, 0.13, 0.13, 0.12, 0.12, 0.24])

    table_page(pdf, "v7 vs MA2 素の質（ボラ10%/年に正規化して比較）",
        ["指標", "v7（円月曜LONG）", "MA2（金+指数TSMOM）"],
        [["Sharpe", "1.47", "0.45"],
         ["CAGR", "+15.2%", "+4.1%"],
         ["最大DD", "−3.7%", "−16.6%"],
         ["勝率", "62%", "63%"],
         ["v7との相関(10年)", "—", "−0.16（負＝分散先）"]],
        note="素の質はv7が約3倍。ただし相関が負ゆえブレンドでSharpe1.47→1.72に上昇余地。"
             "MA2はLEAD(有意水準未達)＝配分はデモ追検後に少量から。",
        col_w=[0.30, 0.35, 0.35])

    table_page(pdf, "探索済みログ（重複探索を避けるための全REJECT一覧）",
        ["doc", "系統", "結果"],
        [["14", "曜日・ターンオブマンス 全9ペア", "月曜JPY以外なし"],
         ["17", "v8 USDCHF木曜SHORT", "10年REJECT・EA削除"],
         ["20", "ゴトー日/TOM 5候補", "全REJECT(−13〜−16%)"],
         ["21", "平均回帰 4候補", "全REJECT・ADOPTゼロ"],
         ["22", "時系列モメンタムFX 6系統", "全REJECT・LEADゼロ"],
         ["23", "多資産トレンド 6候補", "LEAD×3・ADOPTゼロ"]],
        note="FX内のカレンダー・順方向・平均回帰・モメンタムは検出力十分で全滅。"
             "3本目・4本目は『同じ土俵を繰り返さず未踏領域』を事前登録して探索すること。",
        col_w=[0.10, 0.50, 0.40])

p2_size = os.path.getsize(p2)
print("OK")
print(p1, p1_size, "bytes")
print(p2, p2_size, "bytes")
