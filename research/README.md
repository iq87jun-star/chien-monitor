# research — FXプロップ・エッジ研究

統計的エッジの**事前登録 → 10年検定 → 全6ゲート判定**のためのコード。
規律は `docs/26_preregistration_edge3_edge4.md`（および引き継ぎプロンプト）に従う。

## 状態（2026-06-02）
- **3本目・4本目エッジ**を探索中。事前登録 `docs/26` は **LOCKED（2026-06-02 承認済）**。
- E3A〜E3D の runner 実装済み。`smoke_test.py`（合成）PASS、かつ **実 Dukascopy データ（2020上期）で
  端から端まで動作確認済**（fetch→v7→4本→JSON）。**拘束力ある10年判定は未実施** — 10年フル取得後に確定。
- データ未存在問題は解消: `fetch_data.py` で Dukascopy から自前取得する方式に。
- 既存の検証済みコア = **v7**（月曜JPYクロスLONG多ショット）。詳細は提供PDF。
- 注: 前セッションの `docs/14〜25`・旧 `research/*.py`・`reports/*.pdf` は本リポジトリに
  未コミットで存在しない。現状は提供資料（PDF2/EA2/引き継ぎ）から再構成。

## レイアウト
```
research/
  fetch_data.py          # Dukascopy から FX13+指数3 の H1 を取得（live 動作確認済）
  build_v7_weekly.py     # v7 を H1 から再現し v7_weekly_returns.csv を生成（ゲート⑥基準）
  build_policy_rates.py  # BIS から G10 政策金利を自動取得（E3C用・live 動作確認済）
  edge_harness.py        # 汎用6ゲート検定エンジン（候補非依存・実装済・自己テスト済）
  data_io.py             # Drive/ローカル両対応のデータロード（EDGE_DATA_DIR / EDGE_REPORTS_DIR）
  data/README.md         # データ取得手順＋要件
  data/costs.csv         # 往復コスト/スワップ（暫定値・要ブローカー実値）
  data/policy_rates_monthly.csv  # E3C 用・BIS実値（build_policy_rates.py 生成・committed）
  edge3a_eqmr_10y.py     # E3A 株価指数 短期MR
  edge3b_leadlag_10y.py  # E3B クロスアセット・リードラグ
  edge3c_carry_10y.py    # E3C 横断キャリー（スポットのみ・de-swap）
  edge3d_session_10y.py  # E3D ボラ条件付きセッション・ブレイク
  smoke_test.py          # 合成データで4 runner を端から端まで実行（動作確認のみ）
notebooks/edge3_run.ipynb # ★Colab で開いて上から実行 → 4本を回し結果サマリまで出す
docs/                    # 事前登録・検定結果の転記
reports/                 # PDF 化した検証結果
```

## ハーネスの使い方（候補 runner 側）
```python
from edge_harness import Trades, evaluate_edge, write_result_json
# 1. data からトレード列を生成（候補ごとに固定ルール）
trades = Trades(df)   # 必須列: entry_time,exit_time,symbol,direction,ret_gross,cost
# 2. 全6ゲートで評価
res = evaluate_edge("E3A", trades, v7_weekly, risk_budget_pct=0.6,
                    placebo_fn=my_placebo, alpha=0.0125)
# 3. JSON 直読で転記（規律4）
write_result_json(res, "reports/edge3a_result.json")
```

## 自己テスト
```
pip install numpy pandas scipy
python3 research/edge_harness.py   # 既知の正エッジが ADOPT になることを確認
```
