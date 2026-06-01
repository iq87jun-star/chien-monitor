# MQL5 Market 出品メタデータ — TradeCloser

> ビルドは `RG_BUILD_MARKET` を有効化してコンパイル（自前WebRequest無効＝DLL/外部呼び出しなし、規約準拠）。
> 価格：**$39（買い切り）**／有効化数 **10** 推奨。

## 基本情報
| 項目 | 値 |
|---|---|
| Product name | TradeCloser — One-Click Close & Basket Manager |
| Category | Utilities |
| Platform | MetaTrader 5 |
| Price | $39（買い切り） |
| Activations | 10 |

## タグ / キーワード
`close all`, `panic close`, `partial close`, `basket close`, `position manager`, `pending orders`, `risk management`, `utility`, `one click`

## 説明文（English）
```
TradeCloser is a closing and position-management utility for MetaTrader 5. It
never opens trades — it gives you fast, reliable control over closing.

WHAT IT DOES
- Close ALL positions, or only the current symbol
- Close winners only, or losers only
- Partial close by a chosen % to scale out
- Delete all pending orders in one click
- Basket auto-close: close everything when total floating P/L reaches your
  profit target or loss stop (by money or % of balance)
- PANIC button: close all positions and delete all pendings at once
- Scope filters: current symbol only, and/or match a magic number

IMPORTANT
TradeCloser is a utility. It does not open trades, generate signals, predict
markets, or guarantee profit. Trading leveraged products carries a high level
of risk; past performance does not guarantee future results. Test on a demo
account first.
```

## 説明文（日本語・補足欄）
```
TradeCloserはMT5用の決済・ポジション管理ユーティリティです。新規エントリーはしません。

できること
- 全決済／現在銘柄のみ決済
- 勝ちのみ／負けのみ決済
- 部分決済（%指定）
- 待機注文の一括削除
- バスケット自動決済（合計損益が利益目標／損失上限に到達で全決済。金額or残高%）
- PANIC：全決済＋全注文削除を一発
- 対象範囲フィルタ（現在銘柄のみ／マジック一致）

重要
本ツールはユーティリティです。新規エントリー・シグナル生成・相場予測・利益保証は行いません。
取引にはリスクが伴い、過去の成績は将来を保証しません。まずデモ口座でご確認ください。
```

## スクリーンショット撮影リスト
1. パネル全体（7ボタン）＋情報ラベル（scope / basket P/L）
2. CLOSE WINNERS 実行前後（含み益ポジのみ消える様子）
3. CLOSE %（部分決済でロットが縮小）
4. バスケット自動決済の設定（利益目標/損失上限の入力）
5. ライセンス状態 "Market licensed"（Market版）

## 出品前チェック（規約）
- [ ] DLL/外部呼び出しなし（`RG_BUILD_MARKET`）
- [ ] 誇大表現・利益保証なし／リスク開示あり（機能のみ訴求）
- [ ] デモ/トライアルの偽装なし
- [ ] 競合宣伝なし／スクショと実機能が一致
