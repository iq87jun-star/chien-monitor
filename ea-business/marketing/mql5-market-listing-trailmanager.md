# MQL5 Market 出品メタデータ — TrailManager

> ビルドは `RG_BUILD_MARKET` を有効化してコンパイル（自前WebRequest無効＝DLL/外部呼び出しなし、規約準拠）。
> 価格：**$45（買い切り）**／有効化数 **10** 推奨。

## 基本情報
| 項目 | 値 |
|---|---|
| Product name | TrailManager — Trailing Stop & Break-Even for Any Position |
| Category | Utilities |
| Platform | MetaTrader 5 |
| Price | $45（買い切り） |
| Activations | 10 |

## タグ / キーワード
`trailing stop`, `break even`, `ATR trailing`, `stop loss`, `position manager`, `trade manager`, `risk management`, `utility`

## 説明文（English）
```
TrailManager is a position-management utility for MetaTrader 5. It never opens
trades — it manages the stop-loss of positions you already have.

WHAT IT DOES
- Applies a trailing stop to any existing position, including positions opened
  by other tools, other EAs, or manually
- Three trailing modes: FIXED (fixed pips), ATR (volatility-adaptive),
  STEP (moves only in discrete steps to reduce modifications)
- Automatic break-even: move the SL to entry (+lock) after a profit threshold
- Optional initial SL for positions that have none
- Scope filters: current symbol only, and/or match a magic number
- On-chart panel with a Pause/Resume toggle

IMPORTANT
TrailManager is a utility. It does not open trades, generate signals, predict
markets, or guarantee profit. The stop-loss only moves in the favourable
direction. Trading leveraged products carries a high level of risk; past
performance does not guarantee future results. Test on a demo account first.
```

## 説明文（日本語・補足欄）
```
TrailManagerはMT5用のポジション管理ユーティリティです。新規エントリーはしません。

できること
- 既存のどのポジションにもトレーリングを後付け（他ツール・他EA・手動でもOK）
- 3モード：FIXED（固定pips）／ATR（ボラ適応）／STEP（修正回数を抑制）
- 建値移動（含み益が閾値でSLを建値へ）
- SLが無いポジションへ初期SLを付与（任意）
- 対象範囲フィルタ（現在銘柄のみ／マジック一致）
- パネルでON/OFF切替

重要
本ツールはユーティリティです。新規エントリー・シグナル生成・相場予測・利益保証は行いません。
SLは不利な方向には動きません。取引にはリスクが伴い、過去の成績は将来を保証しません。まずデモ口座でご確認ください。
```

## スクリーンショット撮影リスト
1. パネル（モード・managing件数・ON/OFF）
2. FIXEDモードでSLが建値→トレーリングで追従する様子
3. ATRモードの設定（期間・倍率・時間足）
4. 手動で建てたポジションが管理対象になっている様子
5. ライセンス状態 "Market licensed"（Market版）

## 出品前チェック（規約）
- [ ] DLL/外部呼び出しなし（`RG_BUILD_MARKET`）
- [ ] 誇大表現・利益保証なし／リスク開示あり（機能のみ訴求）
- [ ] デモ/トライアルの偽装なし
- [ ] 競合宣伝なし／スクショと実機能が一致
