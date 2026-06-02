# research — FXプロップ・エッジ研究

統計的エッジの**事前登録 → 10年検定 → 全6ゲート判定**のためのコード。
規律は `docs/26_preregistration_edge3_edge4.md`（および引き継ぎプロンプト）に従う。

## 状態（2026-06-02）
- **3本目・4本目エッジ**を探索中。事前登録 `docs/26` は **LOCKED（2026-06-02 承認済）**。
- E3A〜E3D の runner 実装済み。合成データで端から端まで `smoke_test.py` PASS（落ちずに JSON 出力）。
  **拘束力ある判定は未実施** — ユーザーが Drive の実10年データで実行して初めて確定。
- 既存の検証済みコア = **v7**（月曜JPYクロスLONG多ショット）。詳細は提供PDF。
- 注: 前セッションの `docs/14〜25`・旧 `research/*.py`・`reports/*.pdf` は本リポジトリに
  未コミットで存在しない。現状は提供資料（PDF2/EA2/引き継ぎ）から再構成。

## レイアウト
```
research/
  edge_harness.py        # 汎用6ゲート検定エンジン（候補非依存・実装済・自己テスト済）
  data_io.py             # Drive/ローカル両対応のデータロード（EDGE_DATA_DIR / EDGE_REPORTS_DIR）
  data/README.md         # 10年データ要件（Drive 配置）
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
