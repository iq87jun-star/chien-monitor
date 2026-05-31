# TradeCloser セットアップガイド（日本語）

## 1. インストール
1. `TradeCloser.ex5` を `MQL5/Experts/` に配置（ソース配布の場合は `TradeCloser.mq5` を MetaEditor で開き **F7 コンパイル**）。
   - 本ツールは RiskGuard の `LicenseClient.mqh` を参照します。ソースから使う場合は
     `products/risk-guard/src/LicenseClient.mqh` を相対パスのまま配置するか、同フォルダにコピーしてください。
2. MT5 を再起動 or ナビゲータ更新。
3. 任意のチャートにドラッグ＆ドロップ。

## 2. アルゴリズム取引の許可
- ツールバーの「アルゴリズム取引」を ON。
- 投入ダイアログで「アルゴリズム取引を許可」にチェック。

## 3.（自前販売版のみ）ライセンス設定
1. ツール > オプション > エキスパートアドバイザ で「次のURLのWebRequestを許可する」にチェック。
2. ライセンスURL（例 `https://api.riskguard.app`）を追加。
3. `InpLicenseKey` にキー、`InpLicenseServer` に認証URLを設定。

> MQL5 Market 版は不要です。

## 4. 動作確認
- パネル（CLOSE ALL / SYMBOL / WINNERS / LOSERS / CLOSE % / DEL PENDINGS / PANIC）が表示される。
- 情報ラベルに `scope` と `basket P/L` が表示され、状態が「Licensed」/「Market licensed」。
- **まずデモ口座**でボタン動作・バスケット自動決済を確認してください。
