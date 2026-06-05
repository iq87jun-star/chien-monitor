# chien-monitor — FundedNext Stellar 2-Step ($100K) 通過特化EA

FundedNext「Stellar 2-Step」チャレンジ（$100,000 / Phase1）を、規則を完全遵守しつつ
**失格(退場)回避を最優先**に通過確率を最大化するための MQL5 EA 一式。

> **重要な更新（v2）**: v1 の「トレンド×押し目RSI反転」ロジックは、ユーザーの厳密な実データ検証
> (Lv1–Lv5: ノールックアヘッド/実コスト/OOS/ブートストラップ/Bonferroni) で **全7ペア エッジ無し** と判明。
> 白紙から再探索した結果、**日足RSI平均回帰(逆張り)** だけがエッジの兆候を示したため v2 として実装した。
> ただしこのエッジは**レジーム依存**（直近数年は強いが2016–21は負け）という重大な限界がある。
> 詳細は [`docs/04_research_v2_findings.md`](docs/04_research_v2_findings.md)。**本番前にユーザーの実データハーネスで要再検証。**
> v1 ロジックは本番投入しないこと。

## 成果物

| ファイル | 内容 |
|---|---|
| [`docs/01_challenge_rules_summary.md`](docs/01_challenge_rules_summary.md) | ① 条件要約・ドローダウン計算方式の確定（日次5%/最大10%、equity即時判定、00:00サーバリセット） |
| [`docs/02_strategy_spec.md`](docs/02_strategy_spec.md) | ② 戦略仕様（タイプ比較・銘柄/時間足・エントリー・SL/TP・ガード階層・コスト・通過逆算） |
| [`mql5/FundedNext_Stellar_EA.mq5`](mql5/FundedNext_Stellar_EA.mq5) | ③ v1 EA本体（トレンド押し目。**実データでエッジ無し→本番非推奨**。ガード実装の参照用） |
| [`mql5/FundedNext_Stellar_EA_v2.mq5`](mql5/FundedNext_Stellar_EA_v2.mq5) | ③' v2 EA（RSI日足逆張り。**実データでレジーム依存→棄却**。参照用） |
| [`mql5/presets/v2_RSI_meanrev_default.set`](mql5/presets/v2_RSI_meanrev_default.set) | v2 プリセット |
| [`mql5/FundedNext_Stellar_EA_v3.mq5`](mql5/FundedNext_Stellar_EA_v3.mq5) | ③'' **v3 EA（多信号アンサンブル k≥4）**。研究で唯一プールP値が有意。同ガード継承。**要再検証** |
| [`mql5/presets/v3_confluence_default.set`](mql5/presets/v3_confluence_default.set) | v3 既定プリセット（k≥4合議） |
| [`mql5/FundedNext_Stellar_EA_v9.mq5`](mql5/FundedNext_Stellar_EA_v9.mq5) | ③''' **v9 EA（月曜・週末フロー intraday 12h・同日決済）**。v7と同エッジを**DDほぼ半減・スワップリスク排除**で運用。同ガード継承。**要10年再測** |
| [`mql5/presets/v9_intraday_default.set`](mql5/presets/v9_intraday_default.set) | v9 既定プリセット（12h保有・保守予算0.60・等加重） |
| [`docs/37_v9_intraday_weekendflow.md`](docs/37_v9_intraday_weekendflow.md) | ⑥ v9研究（新シグ探索=TOM/金曜SHORT棄却→月曜エッジ再確認→12h保有でCalmar最良の実証） |
| [`docs/04_research_v2_findings.md`](docs/04_research_v2_findings.md) | ⑤ v2研究レポート（Lv1-5でv1否定→白紙再探索→S3採用、感度/WF/Bonferroni） |
| [`research/`](research/) | 研究用バックテスタ・戦略スクリーニング・ロバスト性検証（実データ） |
| [`mql5/presets/EURUSD_default.set`](mql5/presets/EURUSD_default.set) | v1 EURUSD 既定プリセット |
| [`sim/montecarlo_challenge.py`](sim/montecarlo_challenge.py) | チャレンジ動態モンテカルロ（Phase1単体・依存なし） |
| [`sim/montecarlo_2phase.py`](sim/montecarlo_2phase.py) | P1→P2連続＋連敗自己相関ストレスのモンテカルロ |
| [`docs/03_validation_report.md`](docs/03_validation_report.md) | ④ 検証レポート（MC実数値＋実価格WFA設計＋過剰最適化点検） |

## 4本目エッジ探索（docs/47-48）— 誠実な NEGATIVE：Portfolio3 が最終形

3本目（v7+v4+E5 の Portfolio3）完成を受け、**第4の独立エッジ**を探索した。日足・月次・カレンダー・
リードラグ系は枯渇済み（docs/14,27,42）のため、docs/27 §4 の指示通り **未踏の足内(H1)条件付き3構造**を
**事前登録**（[`docs/47`](docs/47_4thedge_preregistration.md)・候補とBonferroni母数を実行前に固定）→
予備スクリーニング（[`research/edge10_4thedge.py`](research/edge10_4thedge.py)・Yahoo H1 ~2年）した。

| 候補 | 内容 | プール純益 | OOS boot_p | 判定 |
|---|---|--:|--:|---|
| C1 インパルス・フェード | 足内2σ超→逆張り | −430.6% | 1.000 | **REJECT** |
| C2 圧縮ブレイク | アジア圧縮→London抜け | −15.0% | 0.998 | **REJECT** |
| C3 アジア→London反転 | 前セッション過大→反転 | −45.2% | 0.991 | **REJECT** |

→ **3候補とも棄却（フェードも継続も負＝方向エッジ無し・コスト負け）。第4の独立エッジは現データに無い**
（[`docs/48`](docs/48_4thedge_findings.md)）。**∴ Portfolio3（v7+v4+E5・互いに低/負相関）を最終形とするのが
誠実な結論**。10年での正式確定が要れば [`research/colab_edge10_4thedge_10y.py`](research/colab_edge10_4thedge_10y.py)
を Drive 実行（予備が決定的に負ゆえ優先度は低い）。収益拡大は新エッジでなく Portfolio3 のサイズ最適化＋
デモ前進検証（docs/29,44）で。

## 検証ハイライト（モンテカルロ 50,000×3シナリオ）

- **全シナリオ・全勝率で 日次DD失格＝0.000% / 最大DD失格＝0.000%**（ガードの構造的成果）。
- 通過はエッジ依存: 現実コスト下で **勝率45%/RR1.8 → 通過率80%超、勝率50% → 約98%**。
- 高コスト($105/lot)はSL拡大(スイング化)で緩和（勝率50%: 22% → 82%）。
- **連敗自己相関(マルコフ)＋P1→P2連結ストレスでも失格 0.000%**。連続通過は現実コスト・勝率50%で約93%。

```bash
python3 sim/montecarlo_challenge.py   # Phase1単体（シード固定）
python3 sim/montecarlo_2phase.py      # P1→P2連続＋連敗相関ストレス
```

## 使い方（MT5）

1. `FundedNext_Stellar_EA.mq5` を MetaEditor でコンパイル。
2. EURUSD H1 チャートに適用し `EURUSD_default.set` を読み込み。
3. Phase2 では `InpProfitTargetPct=5.0` に変更。実コストをテスター/口座条件に合わせて入力。
4. 本番前に `docs/03_validation_report.md` B章の実価格ウォークフォワードを実施。

> **免責**: バックテスト/シミュレーションは将来の成績・ライブ約定を保証しない。「必ず通る手法」は存在しない。
> 本EAはリスクガードで退場確率を極小化するが、利益はエッジに依存する。運用前に最新の FundedNext 規約を再確認すること。
