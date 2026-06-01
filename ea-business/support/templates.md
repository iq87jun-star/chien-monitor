# サポート定型回答テンプレート（RiskGuard）

> 自動対応 → 人間エスカレーションの切り分けは `flow.md` 参照。
> 利益保証・投資助言は絶対にしない。

## 1. 発注されない（最頻）
> ご連絡ありがとうございます。次をご確認ください：
> 1. ツールバーの「アルゴリズム取引」がONか
> 2. `InpStopLossPips` が0でないか（0だと安全のため発注しません）
> 3. スプレッドが `InpMaxSpreadPts` 以内か
> 4. チャート左上のライセンス状態が有効か
> 5. 計算ロットが0でないか（リスク%・SL・余剰証拠金）
> 解決しない場合、MT5の「エキスパート」ログのスクショをお送りください。

## 2. ライセンスエラー（自前販売版）
> WebRequestの許可設定をご確認ください：ツール > オプション > エキスパートアドバイザ で、ライセンスURLを許可リストに追加してください（setup-ja.md 参照）。それでも解決しない場合、入力した `InpLicenseKey` と口座番号をお知らせください（パスワードは送らないでください）。

## 3. ロットが想定と違う
> ロットは「残高 × リスク% ÷（SL幅×1ロット損失）」で算出されます。SLを広げるとロットは小さくなります。固定ロットにするには `InpFixedLot` をご設定ください。

## 4. 返金依頼
> 返金は販売チャネルの規約に従います。まず不具合の詳細（症状・ログ・スクショ）をお送りいただければ、解決を試みます。← **金額・規約判断は人間にエスカレーション**

## 5. 「勝てますか？」系
> RiskGuardはリスク管理と発注を補助するツールで、相場予測や利益保証は行いません。デモ口座で挙動をご確認のうえご判断ください。

---

### English quick replies
- **No orders fire:** check Algo Trading ON, SL ≠ 0, spread within limit, license valid, computed lot > 0. Send the Experts log screenshot if unresolved.
- **License error (self-hosted):** whitelist the license URL in Tools > Options > Expert Advisors. Then send your key + account number (never your password).
- **Refund:** follows the sales channel's policy → escalate amount/policy decisions to a human.
