# chien-monitor — FundedNext Stellar 2-Step ($100K) 通過特化EA

FundedNext「Stellar 2-Step」チャレンジ（$100,000 / Phase1）を、規則を完全遵守しつつ
**失格(退場)回避を最優先**に通過確率を最大化するための MQL5 EA 一式。

> **重要な更新（v2）**: v1 の「トレンド×押し目RSI反転」ロジックは、ユーザーの厳密な実データ検証
> (Lv1–Lv5: ノールックアヘッド/実コスト/OOS/ブートストラップ/Bonferroni) で **全7ペア エッジ無し** と判明。
> 白紙から再探索した結果、**日足RSI平均回帰(逆張り)** だけがエッジの兆候を示したため v2 として実装した。
> ただしこのエッジは**レジーム依存**（直近数年は強いが2016–21は負け）という重大な限界がある。
> 詳細は [`docs/04_research_v2_findings.md`](docs/04_research_v2_findings.md)。**本番前にユーザーの実データハーネスで要再検証。**
> v1 ロジックは本番投入しないこと。

> **第2ポートフォリオ(P2)を追加（[`docs/50`](docs/50_p2_turnofweek_portfolio.md)）**:
> 既存P1(v7円月曜＋v4合議FX＋E5多資産モメンタム)とは**別物の分散源**として、商品ユニバースを拡張し
> （追加FXクロス＋金属＋株価指数＋暗号, Yahoo10年）同じ9ゲートで全数検定。
> 生き残ったのは **米独株価指数(US500/NAS100/GER40)の「月曜LONG」(週初ドリフト)バスケット** ＝
> **STRONG-LEAD（P1のv7/E5と同級。月曜のみ有意のプラセボ識別・IS/OOS両+・WF4/5・コスト2×+、未達はBonf/JKのみ）**。
> 決定的に **P1との月次相関=0.014（ほぼゼロ）** で、同ボラ併用すると **Sharpe 1.06→1.23・maxDD −4.7%→−3.2%**。
> EA: [`mql5/Chien_P2_TurnOfWeek_AllInOne.mq5`](mql5/Chien_P2_TurnOfWeek_AllInOne.mq5)（1チャート挿入・Magic940800・P1と別系統）。
> 実データ追認: [`research/colab_p2_validate.py`](research/colab_p2_validate.py)。**本資金前にデモ前進検証（P1と同方針）。**

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
