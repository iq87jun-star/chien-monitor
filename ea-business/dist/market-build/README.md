# Market-build sources（MQL5 Market 出品用）

このフォルダは **MQL5 Market 出品用にビルド設定済み**のソースです。
`#define RG_BUILD_MARKET` が有効＝**自前ライセンス（WebRequest）を呼ばない**ため、
DLL/外部呼び出し禁止の Market 規約に準拠します。ライセンスはMQL5プラットフォームが管理。

## コンパイル
製品ごとにフォルダ単位で `MQL5/Experts/` に置き、`.mq5` を MetaEditor で F7：
```
MQL5/Experts/RiskGuard/    ← RiskGuard.mq5  + LicenseClient.mqh
MQL5/Experts/TradeCloser/  ← TradeCloser.mq5 + LicenseClient.mqh
```
生成された `.ex5` を MQL5 Market の出品ページからアップロードします。

## 出品メタデータ
- RiskGuard  : `../../marketing/mql5-market-listing.md`
- TradeCloser: `../../marketing/mql5-market-listing-tradecloser.md`

## 注意
- `products/*/src/` 側は **自前販売版（RG_BUILD_SELF）** のままです（用途で使い分け）。
- Market版はライセンス入力（InpLicenseKey等）が実質無効になります（プラットフォーム管理）。
