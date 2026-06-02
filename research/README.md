# research/ — 統計的エッジ研究ハーネス

FXプロップ運用のための事前登録ハーネス群。**拘束力ある10年検定はユーザーのGoogle Drive
（Colab）で実行**する。スクリプトは Drive / ローカル両対応（`USE_DRIVE` フラグ）。

## データ規約（Colab=Drive / ローカル=フォールバック）
- FX H1   : `DRIVE_BASE/dukascopy_data_h1/<PAIR>_h1.csv` （無ければ `./research/data/<PAIR>_h1.csv`）
- 多資産日足: `DRIVE_BASE/multiasset_daily/<NAME>_d.csv` （無ければ `./research/data/<NAME>_d.csv`）
- `DRIVE_BASE = /content/drive/MyDrive/forex_ml`
- 多資産日足(XAUUSD/US500/NAS100/GER40/BTCUSD/ETHUSD)は edge5 のデータ取得セル(Yahoo)で生成。

## ハーネス
| ファイル | 内容 |
|---|---|
| `edge6_leadlag_session_10y.py` | **3本目・4本目** 事前登録。クロスアセット・リード/ラグ(LL1-3)＋セッション・ブレイクアウト(SB1-3)。N=6・Bonferroni α=0.0083・6ゲート全通過のみADOPT。事前登録は docs/26。 |

## 6ゲート（edge5 と同一エンジン）
順列p(月次ブロック符号シャッフル=自己相関頑健) / ジャックナイフ最大p≤0.10 / IS・OOS両正 /
v7との月次相関|corr|≤0.4 / プラセボ非有意かつ対象が上回る / 往復1-4pipコストで生存。

## 規律（docs/25）
事前登録(N固定・当てるまで増やさない) ／ 検定は10年実データのみ(短期は楽観側) ／
全ゲート通過のみADOPT ／ 数値はJSON直読で転記 ／ 通らなければ「なし」と正直に結論 ／
-10%口座に収まるサイズで実測し本資金即投入は禁止。

⚠ 全てシミュレーション。将来を保証しない。
