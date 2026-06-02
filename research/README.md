# research/ — 3本目・4本目エッジ探索ハーネス

docs/26（引き継ぎ）と docs/27（事前登録）の規律をコードに固定したもの。
**拘束力ある10年検定はユーザーの Google Drive 実行**（ローカル CSV は短期/一部のみ）。

## 構成

```
lib/
  data.py         CSV ローダ（Drive / ローカル自動解決）
  stats.py        自己相関頑健な順列検定・ジャックナイフ・プラセボ・相関
  engine.py       イベント・スタディ型バックテスタ + プロップ MC 合格率
  v7_reference.py v7（月曜JPYクロス）週次 R の再現（相関ゲート用）
  evaluate.py     6 ゲート判定 → ADOPT/LEAD/REJECT、単一スカラ JSON 出力
edge3_vol_regime_10y.py        E3 VIX レジーム → XAUUSD
edge4_rates_jpy_leadlag_10y.py E4 US2Y → USDJPY 先行
edge5_event_drift_10y.py       E5 FOMC/BOJ 翌日ドリフト
edge6_index_meanrev_10y.py     E6 SPX オーバーナイト平均回帰
tests/smoke_test.py            合成データでの動作確認（検定ではない）
```

## データ置き場

解決順: `CHIEN_DATA_DIR` → `/content/drive/MyDrive/chien-monitor/data` → `research/data`

| ファイル | 用途 | 列 |
|---------|------|----|
| `<SYM>_h1.csv` | FX H1（EURJPY/GBPJPY/USDJPY ほか） | `time,open,high,low,close[,spread]` UTC |
| `<SYM>_d.csv` | 日足/多資産（XAUUSD/SPX/VIX/US2Y/USDJPY） | `time,open,high,low,close` |
| `events_cb_d.csv` | 中銀イベント（E5） | `time,kind`（kind∈FOMC,BOJ） |

## 実行（★事前登録の承認後）

```bash
export CHIEN_DATA_DIR=/content/drive/MyDrive/chien-monitor/data   # Colab
python3 research/edge3_vol_regime_10y.py        # -> reports/edge3_result.json
python3 research/edge4_rates_jpy_leadlag_10y.py
python3 research/edge5_event_drift_10y.py
python3 research/edge6_index_meanrev_10y.py
```

各スクリプトは `reports/edgeN_result.json` に**単一スカラ**（verdict / 6 gates / perm_p /
jackknife_max_p / v7_corr / net_R / MC合格率）を出力。表示破損のまま転記しない。

## スモークテスト（合成データ・依存確認）

```bash
pip install numpy pandas
python3 research/tests/smoke_test.py     # ALL SMOKE TESTS PASSED が出れば OK
```

## 6 ゲート（evaluate.py）

1. 純益>0  2. 順列 p<α(=0.0125)  3. ジャックナイフ最大 p≤0.10
4. プラセボで対象だけ突出  5. コスト計上後も純益>0  6. v7 相関 |≤0.30|
→ 全通過のみ **ADOPT**。p が 0.0125〜0.10 の惜しい圏で G1・G3・G6 通過なら **LEAD**。それ以外 **REJECT**。

> 免責: 数値はシミュレーション（10年実測ベース）。将来を保証しない。
