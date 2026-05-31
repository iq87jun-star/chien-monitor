# RiskGuard — パフォーマンス資料

> RiskGuard は**手動トレード補助ツール**（シグナル生成なし）のため、純粋な戦略バックテストの対象ではありません。
> ここには「ロット計算の妥当性」「トレーリング挙動」の検証メモや、(主力EA商品化フェーズで) 戦略EAのテスト結果を置きます。

## バックテスト資料の自動生成
MT5 ストラテジーテスタが出力する HTML レポートから、コンプラ準拠（免責文を必ず挿入）の要約Markdownを生成：

```bash
python ../../../scripts/gen_report.py ReportTester.html -o summary-ja.md --lang ja
python ../../../scripts/gen_report.py ReportTester.html -o summary-en.md --lang en
```

## ルール
- 公開資料には**必ずリスク開示・免責**を入れる（スクリプトが自動挿入）。
- 「必ず勝てる」「月利保証」等の表現は使わない。
- バックテストはリアル取引の成果を保証しない旨を明記する。
