# -*- coding: utf-8 -*-
"""build_p2_notebook.py — P2(株価指数 週初ロング)検証を1ファイルで完結する .ipynb を生成。

notebooks/p2_validate.ipynb を出力。Colabで「すべて実行」すれば、ユーザーのDrive実指数
(あれば最優先)または Yahoo フォールバックで、P2核を P1のv7基準 9ゲートで採点し、さらに
独立インストゥルメント(現物/ETF/先物)で月曜エッジを追認する。各code cellは自己完結。
中身は research/colab_p2_validate.py と research/p2_confirm_proxies.py を埋め込む(同期維持)。
"""
import os
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

HERE=os.path.dirname(os.path.abspath(__file__))
def read(p): return open(os.path.join(HERE,p),encoding="utf-8").read()

cover = r"""# 第2ポートフォリオ(P2) 検証 — 「ターン・オブ・ウィーク株価指数」バスケット

既存P1(v7円月曜＋v4合議FX＋E5多資産モメンタム)とは**別物・低相関**な第2ポートフォリオ(P2)を、
P1と**同一の v7基準 9ゲート**で採点する自己完結ノート。詳細は `docs/50_p2_turnofweek_portfolio.md`。

## 採用エッジ
**米独株価指数(US500 / NAS100 / GER40)の「月曜LONG」(週初ドリフト)バスケット**
= STRONG-LEAD(P1のv7/E5と同級)。**P1との月次相関 0.014(ほぼゼロ)** が最大の価値。

## 🚀 使い方（Colab）
1. （実データ確証する場合）Google Drive の `MyDrive/forex_ml/multiasset_daily/` に
   `US500_d.csv` / `NAS100_d.csv` / `GER40_d.csv`(列: timestamp,open,high,low,close, 日足10年)を置く。
   無ければ **Yahoo(^GSPC/^IXIC/^GDAXI)を自動取得**(研究用フォールバック)。
2. 「ランタイム → すべてのセルを実行」。
3. 第1セル=9ゲート採点(判定 STRONG-LEAD)、第2セル=独立インストゥルメント追認(現物/ETF/先物 8/8)。

## このノートが答える問い
- 月曜LONGは**月曜に特異か**(プラセボ: 火-金は非有意か)？
- IS/OOS両+ / 年次JK / ウォークフォワード / コスト2× を通るか？
- **P1と独立か**(相関≈0)？ −10%枠に収まるサイズは(チャレンジMC)？
- 現物だけでなく**ETF・先物でも再現**するか(Yahoo現物固有のクセでない傍証)？

> ⚠ シミュレーション。株価指数=配当抜きprice index。CFD実スプレッド/オーバーナイトスワップ/配当は
> 未計上＝**デモで実測**。最終確証はユーザーの実データ・デモ前進検証で(P1と同方針)。「必ず通る手法」は無い。
"""

setup = r"""# 依存(Colabは標準で入っているが念のため)
!pip -q install numpy pandas >/dev/null 2>&1
print("ready")"""

md_validate = r"""## 1. 本検証 — P1のv7基準 9ゲートで P2核を採点
`research/colab_p2_validate.py` と同一。Drive実指数があれば最優先、無ければYahoo自動取得。"""

md_confirm = r"""## 2. 独立インストゥルメント追認（現物 / ETF / 先物）
同じ指数を ETF(SPY/QQQ/EWG)・先物(ES/NQ) で再検定。月曜のみ有意が再現すれば
「Yahoo現物固有のクセ」でなく本物の市場現象の傍証。先物再現はCFD実運用妥当性も補強。
`research/p2_confirm_proxies.py` と同一。"""

nb=new_notebook()
nb.cells=[
    new_markdown_cell(cover),
    new_code_cell(setup),
    new_markdown_cell(md_validate),
    new_code_cell(read("colab_p2_validate.py")),
    new_markdown_cell(md_confirm),
    new_code_cell(read("p2_confirm_proxies.py")),
]
nb.metadata={"colab":{"provenance":[]},
             "kernelspec":{"display_name":"Python 3","name":"python3"},
             "language_info":{"name":"python"}}
out=os.path.join(HERE,"..","notebooks","p2_validate.ipynb")
out=os.path.abspath(out)
with open(out,"w",encoding="utf-8") as f:
    nbf.write(nb,f)
print("生成:",out,"cells=",len(nb.cells))
