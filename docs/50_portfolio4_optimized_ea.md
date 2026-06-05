# 50. 最適化ポートフォリオEA `Chien_Portfolio4_Optimized.mq5` — 1チャートで最適比率を運用

> docs/49 のスイープ最適（3戦略比率 v7:v4:E5）を**そのままデプロイできる新EA**。既存 Portfolio3 の
> 実績エンジン・口座ガードを**逐語継承**し、シナリオ部だけを「目的別×ルール別」の最適化プリセットに
> 差し替えた（トレーディングロジックは無変更＝挙動は検証済みと同一）。

## 0. これは何か（旧 Portfolio3 との違い）

| 項目 | 旧 Chien_Portfolio3_AllInOne_INSTANT/_PROP | 新 **Chien_Portfolio4_Optimized** |
|---|---|---|
| 比率 | 40:40:20（手置き概算・2ファイル固定） | **目的別プリセット**（docs/49 最適。既定=Calmar最大 40:35:25）|
| ルール | ファイルで固定（INSTANT or PROP） | **1ファイルで InpRuleMode 切替**（INSTANT/PROP）|
| ガード | −10%枠の内側で全停止 | 同一（無変更）＋**E5≤25% ガード**内蔵 |
| エンジン | v7+v4+E5（Magic分離） | **同一（逐語継承）** |

→ **1ファイルで「目的×口座ルール」を選ぶだけ**。比率・サイズ・ルールが自動で入る。

## 1. 使い方（MT5）

1. `mql5/Chien_Portfolio4_Optimized.mq5` を MetaEditor でコンパイル(F7)。
2. 「アルゴリズム取引」ON。**どれでもいいチャート1枚**に本EAをドラッグ → 「Allow Algo Trading」✓ → OK。
3. `InpObjective` と `InpRuleMode` を選ぶ（既定＝**CALMAR × INSTANT**）。残高は自動取得。
   - 銘柄名が業者で違う場合のみ `InpYen/InpV4/InpE5 Symbols` を実名に（US500=SPX500, NAS100=USTEC,
     GER40=DE40, XAUUSD=GOLD 等。別名総当りも内蔵）。
4. **1チャートに1つだけ**（複数や他EAと同口座でMagic衝突回避）。

## 2. プリセット（InpObjective）— docs/49 の最適点

| Objective | 比率 v7:v4:E5 | 位置づけ | CAGR / 5年失格 / Calmar* |
|---|---|---|---|
| **CALMAR（既定★）** | **40:35:25** | **Calmar最大＝推奨** | 6.11% / 1.17% / **0.769** |
| CAGR | 45:35:20 | 手取り最大（やや攻め） | 6.12% / 1.27% / 0.769 |
| DEFENSE | 45:40:15 | E5を絞りモデルリスク最小 | 5.73% / 1.18% / 0.721 |
| BASELINE | 40:40:20 | 旧Portfolio3（参照/移行） | 5.92% / 1.25% / 0.744 |
| MANUAL | 手動値 | InpWeekly/V4/E5 を直接指定 | — |

\* 目標 p95 maxDD=−8%・Blueber −10%トレーリング・MC(docs/49)。**差は誤差内ゆえ既定CALMARで十分**。

## 3. 自動で入る予算（シェア按分・docs/45実値にアンカー）

| Objective × Rule | v7週次% | v4/trade% | E5 legRisk% |
|---|--:|--:|--:|
| CALMAR × INSTANT（既定） | 0.600 | 0.131 | 0.375 |
| CALMAR × PROP | 1.000 | 0.219 | 0.625 |
| DEFENSE × INSTANT | 0.675 | 0.150 | 0.225 |
| BASELINE × INSTANT（=旧P3） | 0.600 | 0.150 | 0.300 |

- これは比率を実現する**相対サイズ**。**絶対倍率は近似値**＝Drive10年(`colab_optimize_portfolio3_10y.py`)
  ＋デモ実DDで確定（docs/49 §4）。攻守は `InpMaxLossLimitPct`/`InpAccountFloorDDPct` と倍率で管理。

## 4. プリセット.set（`mql5/presets/`）
- `p4_calmar_40_35_25_instant.set` … ★推奨（Blueber等）
- `p4_calmar_40_35_25_prop.set` … プロップ突破（FN/FTMO）
- `p4_defensive_45_40_15_instant.set` … 守り最優先

## 5. 必ず守る（本資金前）
- **v4=ADOPT（実10年6/6）だがデモ前進検証必須。E5=STRONG-LEAD（未検証）＝E5≤25%ガードを維持**。
  `InpAcknowledgeLEAD=true` で承認（デモ/極小）。
- 指数/金CFDの実スプレッド/スワップ/配当は未計上 → デモで実測（docs/39）。
- デモで **v7+v4+E5併用の実maxDDが−10%内**か数ヶ月確認 → 合格後に小サイズ本番（まず守り型）。

> 免責: シミュレーション・確率であり保証ではない。比率は最適化済みだが絶対サイズはDrive＋デモで確定。
> 業者規約・銘柄名は要確認。−10%ガードが最終backstop。
