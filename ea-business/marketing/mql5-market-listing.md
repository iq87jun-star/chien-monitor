# MQL5 Market 出品メタデータ — RiskGuard

> ビルドは `RG_BUILD_MARKET` を有効化してコンパイル（自前WebRequestは無効＝DLL/外部呼び出しなし、規約準拠）。
> 価格：**$49（買い切り）**／最低価格$30を満たす。有効化数（activations）はseller指定で **10** を推奨（買い手の複数端末用、規約範囲5〜20）。

## 基本情報
| 項目 | 値 |
|---|---|
| Product name | RiskGuard — Risk % Lot Sizing & Trade Manager |
| Category | Utilities（補助ツール。シグナル生成しないためEAカテゴリでも"utility"性質） |
| Platform | MetaTrader 5 |
| Price | $49（買い切り） |
| Activations | 10 |
| Demo | テスター動作（手動ツールのためテスターでの挙動説明を明記） |

## タグ / キーワード
`risk management`, `lot size`, `position size`, `money management`, `trade manager`, `trailing stop`, `break even`, `one click trading`, `utility`

## 説明文（English）
```
RiskGuard is a manual-trading assistant for MetaTrader 5. You decide the entry;
RiskGuard handles the risk mechanics.

WHAT IT DOES
- Sizes your position automatically from a fixed account-risk % (or a fixed lot)
- One-click BUY / SELL with Stop Loss and Take Profit (TP as an R multiple)
- Moves the stop to break-even and applies a trailing stop automatically
- Spread guard: skips entries when the spread is too wide
- On-chart panel (BUY / SELL / CLOSE ALL); supports 3- and 5-digit quotes

WHO IT'S FOR
Discretionary traders (breakouts, JPY crosses, etc.) who want to mechanize
position sizing and trade management and execute faster.

IMPORTANT
RiskGuard does NOT generate signals and does NOT trade on its own. It is a
position-sizing and order-management tool. It does not predict markets and
provides no guarantee of profit. Trading leveraged products carries a high
level of risk; past performance does not guarantee future results. Test on a
demo account first.

INPUTS
Risk %, fixed lot, SL (pips), TP (R multiple), break-even, trailing, spread
guard, slippage, magic number. See the manual for details.
```

## 説明文（日本語・補足欄用）
```
RiskGuardはMT5用の手動トレード補助ツールです。エントリー判断はあなた、リスク管理はRiskGuard。

できること
- 口座リスク%から適正ロットを自動計算（固定ロットも可）
- BUY/SELLボタンでSL・TP（SLのR倍）付きワンクリック発注
- 建値移動・トレーリングを自動適用
- スプレッドが広い時はエントリー抑止
- チャートパネル（BUY/SELL/CLOSE ALL）、3桁/5桁クォート対応

重要
本ツールはシグナル生成・自動売買は行いません。相場予測・利益保証はしません。
レバレッジ取引にはリスクが伴い、過去の成績は将来を保証しません。まずデモ口座でご確認ください。
```

## スクリーンショット撮影リスト（要・人間が用意）
1. チャート上のパネル（BUY/SELL/CLOSE ALL）と情報ラベル（risk%・計算lot表示）
2. 発注直後：SL/TPラインが入ったポジション
3. トレーリング作動中：SLが追従している様子
4. 入力パラメータ画面（リスク・SL・R倍・トレーリング）
5. ライセンス状態 "Market licensed" の表示（Market版）

## バージョン履歴
- 1.00 初版：リスク%ロット計算、ワンクリック発注、建値移動、トレーリング、スプレッドガード。

## 出品前チェック（規約）
- [ ] DLL/外部呼び出しなし（`RG_BUILD_MARKET`でビルド）
- [ ] 誇大表現・利益保証なし／リスク開示あり
- [ ] デモ/トライアルの偽装表現なし
- [ ] 競合プラットフォーム/有料サービスの宣伝なし
- [ ] スクショ・説明文の内容と実機能が一致
