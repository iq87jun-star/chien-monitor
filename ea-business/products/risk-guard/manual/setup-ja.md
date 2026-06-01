# RiskGuard セットアップガイド（日本語）

## 1. インストール
1. `RiskGuard.ex5`（コンパイル済み）を MetaTrader 5 の `MQL5/Experts/` に配置。
   - ソース配布の場合は `RiskGuard.mq5` と `LicenseClient.mqh` を同じフォルダに置き、MetaEditor で `RiskGuard.mq5` を開いて **F7 でコンパイル**。
2. MT5 を再起動、またはナビゲータを更新。
3. 任意のチャートに `RiskGuard` をドラッグ＆ドロップ。

## 2. アルゴリズム取引の許可
- ツールバーの **「アルゴリズム取引」** を ON。
- EA 投入時のダイアログで「アルゴリズム取引を許可」にチェック。

## 3.（自前販売版のみ）ライセンス認証の設定
WebRequest を使うため、認証サーバのホストを許可リストに追加します。
1. **ツール > オプション > エキスパートアドバイザ** を開く。
2. **「次のURLのWebRequestを許可する」** にチェック。
3. ライセンスサーバのURL（例: `https://license.example.com`）を追加。
4. EA の入力 `InpLicenseKey` に購入時のキー、`InpLicenseServer` に認証URLを設定。

> MQL5 Market 版ではこの手順は不要です（プラットフォームがライセンスを管理）。

## 4. 動作確認
- チャート左上に `RiskGuard | <シンボル> | risk x.xx% | lot x.xx | <状態>` が表示されれば正常。
- 状態が「Licensed」または「Market licensed」であること。
- ライセンス失敗時は画面にメッセージが出て、発注ボタンが無効になります。

## 5. 推奨初期設定（例）
- `InpRiskPercent = 1.0`、`InpStopLossPips = 200`、`InpRiskReward = 1.5`
- まずは**デモ口座**で挙動（ロット計算・SL/TP・トレーリング）を確認してください。
