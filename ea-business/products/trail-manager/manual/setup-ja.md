# TrailManager セットアップガイド（日本語）

## 1. インストール
1. `TrailManager.ex5` を `MQL5/Experts/` に配置（ソース配布なら `TrailManager.mq5` を MetaEditor で開き **F7コンパイル**）。
   - 本ツールは `LicenseClient.mqh` を参照します。ソースから使う場合は同フォルダに `LicenseClient.mqh` を置いてください（同梱）。
2. MT5 を再起動 or ナビゲータ更新。
3. 管理したい銘柄のチャートにドラッグ＆ドロップ。

## 2. アルゴリズム取引の許可
- ツールバーの「アルゴリズム取引」を ON。
- 投入ダイアログで「アルゴリズム取引を許可」にチェック。

## 3.（自前販売版のみ）ライセンス設定
1. ツール > オプション > エキスパートアドバイザ で「次のURLのWebRequestを許可する」にチェック。
2. ライセンスURL（例 `https://api.riskguard.app`）を追加。
3. `InpLicenseKey` にキー、`InpLicenseServer` に認証URLを設定。

> MQL5 Market 版は不要です。

## 4. 動作確認
- パネルに `TrailManager | <銘柄> | mode:FIXED | managing:N | ON` が表示される。
- 既存ポジションに含み益が乗ると、SLが建値→トレーリングで動くこと。
- PAUSE/RESUME で管理が停止/再開すること。
- **まずデモ口座**でFIXED/ATR/STEP各モードの挙動を確認してください。
