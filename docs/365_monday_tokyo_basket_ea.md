# docs/365: 月曜・東京オープン バスケットEA (Chien_MondayTokyo_Prop v1.01)

## 出自
theoptionバイナリー検証(claude/zaption-check-m776m7ブランチ theoption_validation/)で全ゲート合格した
月曜アノマリーのスポット移植。Dukascopy 1時間足 2016-2026/09、家族内Bonferroni+前後半+年抜きJK+順列合格。
ネット期待(往復コスト控除後): EURJPY +10.9p / AUDJPY +9.6p / NZDJPY +6.0p / GBPJPY +4.8p per trade。
OOS(2026年6-9月・検証後データ)もプラス。詳細は同ブランチREADME追補7/12/13。

## 仕様
- 買いのみ: EURJPY/AUDJPY/NZDJPY 日曜22:00GMT(=月曜7:00JST)→月曜21:00GMT(=火曜6:00JST, 23h)
  + GBPJPY 同→日曜23:00GMT(1h)。TimeGMT基準・DST無関係・週1重複ガード
- リスク既定 0.30/0.30/0.25/0.15%(災害SL=2.5×ATR(H1,24)到達時)。月曜同時最大≈1.0%
  → Max Risk 3%/日次5%規約に適合。期待寄与 +1.1〜1.3%/月
- ガード: 日次-4%/フロア-9%/+8%利益停止。実行ログを共有Files/ChienMT_log_<口座>.csvに自動記録
  (probe VPSのchien_mtlog_syncタスクが毎朝06:40にDriveへ同期→毎週火曜7:10の自動突合が回収)

## ⚠併走警告
v7系(円クロス月曜マルチショットUTC4-10)と同一アノマリー。v7稼働口座では
InpLegEURJPY=false, InpLegGBPJPY=false にしてAUDJPY/NZDJPY(v7未使用)のみ追加するか、別口座で。

## 状態
2026-10-20 EA作成・未コンパイル(要MetaEditor)。デモ2週間→週明けスプレッド実測→本番判断。

## 追記 (2026-10-20): v7との相関・限界効果の定量評価

v7近似系列(円3クロス月曜UTC4/6/8/10入り24h・ガードなし素リターン)との比較、556週:
- 新規分(AUDJPY/NZDJPY翌朝 + GBPJPY1h)単独: 週次Sharpe 1.98 (v7近似1.04)
- **v7×新規分の相関 ρ=0.34**(EURJPY翌朝玉を含めると0.41→v7口座ではEURJPY脚OFFが正解)
- 等リスク混合: v7:新規=75:25でSharpe 1.04→1.47(+41%)・maxDD -29%。推奨開始配分=月曜円スリーブの20-25%
- ※v7は近似再構成のため絶対値でなく相対構造(低相関・混合改善)を結論とする。
  正式採否は v7standard 9ゲート + two-book jointloss MC で要裁定(データ: Dukascopy H1 2016-2026/09)
