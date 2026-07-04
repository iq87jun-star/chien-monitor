# 102.【事前登録】edge19b — H19a の別ソース再現(Deribit BTC-PERPETUAL・確認的N=1)

> **位置づけ**: docs/101 §4 が事前固定した昇格ルート①「別ソースfundingでの同一検定」の実行。
> OKXは履歴3ヶ月・Bybitはリージョン403のため、**Deribit BTC-PERPETUAL の funding 履歴**
> (公開API・2019-10〜・時間別, index価格込み)を採用。取引所・参加者・約定機構・価格系列とも
> Binanceから独立(fundingの裁定を通じた相関は残るが、それは「同じ現象の別会場での測定」であり
> v7のYahoo→Dukascopy再現と同じ位置づけ)。数字を見る前に本docを固定しコミットする。

## 1. 凍結ルール(H19a と同一・変更なし)

- **データ**: Deribit `get_funding_rate_history`(BTC-PERPETUAL)の時間別 `interest_8h` と
  `index_price`(2019-10-01〜2026-06-30)。**全てDeribitネイティブ**(Binanceデータ不使用)。
- **シグナル**: F3d = 日t 00:00 UTCまでの直近72時間の `interest_8h` 平均。**F3d < 0 → 翌日LONG**。
- **価格**: 00:00 UTC行の `index_price` を日次値とし、翌日 close-to-close リターンを獲得。
- **コスト**: 片道10bp(基本)・2×ストレス・保有コスト15%/年ストレス(docs/100と同一)。

## 2. 判定(確認的N=1・事前固定)

- **再現成立** = 6ゲート全通過: G-dir / G-p(ドリフト保存プラセボ **α=0.05**, 2000draw)/
  G-split(両半+)/ G-cost(2×)/ G-hold(15%/年)/ G-beta(対ベータ超過+)。
  G-dd はサイズ設計の問題なので**記録のみ**(判定に含めない)。
- 再現成立 → H19a は「**LEAD(別ソース再現済)**」に昇格。ただし **ADOPTではない**。
  EA化・資金投入は昇格条件②(デモ前進6ヶ月)完了後のみ(docs/98 §4)。
- 再現不成立 → H19a は「LEAD(単一ソース・再現失敗)」に**降格**し、docs/98 §4 の監視だけ残す。
  閾値・窓の変更による救済はしない。

## 3. 実行・記録

- `research/edge19b_deribit_replication.py` → `research/results/edge19b_deribit_replication.json`
  (入力SHA-256込み)。結果は docs/103 に実出力の転記のみ。

> 免責: シミュレーション。Deribit index はスポット合成指数であり CFD 執行を近似する。
