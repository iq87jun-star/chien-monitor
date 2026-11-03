# 395.【Q107】紙上フォワード候補 25 本の中間判定を毎月自動化 — docs/229 §4 の規則は不変。経過 1/6 か月(2026-10)で 25 本中 19 本が +・棄却確定 0。時間足系 6 本と HoldSL10 は集計に入っていなかった(2 つの不具合)ので、月次 H1 の継ぎ足しと base.DATA の復元で 10 月から累積に入れた

> docs/322 Q107(工学・セル 0)。2026-11-04 朝 実行。スクリプト `research/forward/candidate_interim.py`、結果 `research/results/candidate_interim_latest.csv`(候補 × 月)。
> 対象: `paper_forward.CANDIDATES` の 25 本(docs/229 §4・303・304・330・333・338・344・347・378 の事前登録セル)。判定窓 2026-10〜2027-03。
> 規則(変更しない): **+月 ≥ 4/6 かつ 累積 > 0 → LEAD、それ未満は棄却**(docs/229 §4)。中間状態は「残り月で 4 勝に届くか」だけを機械的に出す。

## 1. 仕組み

| 部分 | 内容 |
|---|---|
| 日足系 18 本 | 月初の定例 `paper_forward.py` が書く `results/paper_forward_<月>.csv` の「(候補)」行をそのまま読む(再計算しない = 定例と同じ数字)。基準セル(同銘柄の Mon / Hold)との差も同じ CSV から取る |
| 時間足系 6 本(MonIdxIntra ×2・MonJpyIntra6J・MonIdxSession0 ×3・MonJpySession6J・RollGateB2) | 本体 H1(`data_dukascopy/`・2026-08 末まで)に Dukascopy の月次 H1(`forward/q20_monitor_data/<SYM>_<YYYY-MM>_bid.csv`・q20 監視と同じ置き場・無ければ取得)を継ぎ足し、`q_common.load` 系の読込を差し替えて `paper_forward.candidate_series` で再計算 |
| HoldSL10 BTCUSD | `q90` を import すると `base.DATA` が凍結フォルダ `data_202609` に固定される → `data_live` に戻して再計算 |
| 判定 | 候補ごとに +月数・累積・状態(LEAD / 棄却 / 棄却確定 / 継続(あと k 勝・残 n 月))。経過月 = 判定窓のうち完了した月 |
| 定例への組込み | `paper_forward.py` の末尾から自動で呼ぶ(毎月 1 日 06:00 の定例「紙上フォワード月次成績表」で表が一緒に出る)。月次改正案(docs/389 の様式)はこの表を「候補セル」行の根拠にする |

## 2. 見つかった不具合(10 月の表 docs/390 に影響)

1. **時間足系 6 本は 10 月の数字が無かった**(docs/390 で「時間足の再取得を組み込んでから」と注記)。本体 H1 が 2026-08 末で止まっているため。本書で 2026-09・10 の月次 H1(US30 / JP225 / US500 / NAS100 を新規取得、JPY クロスは q20 監視の既存ファイル)を継ぎ足して解消。
2. **HoldSL10 BTCUSD の 10 月が空(data_end 2026-07-29)**: `paper_forward.candidate_series` が `q90_hold_disaster_sl` を import した時点で `base.DATA` が凍結フォルダに固定され、以後その実行内の日足読込がすべて凍結データになる。候補の並びでは HoldSL10 の後ろが時間足系だけだったので他セルへの実害は無かったが、`paper_forward.py` 側も import 直後に `base.DATA` を戻すよう修正した(12/1 の定例から CSV にも正しい値が入る)。

## 3. 結果(経過 1/6 か月・2026-10)

| 族 | 銘柄 | 出所 | 2026-10 % | n | +月 | 累積 % | 状態 | 基準 | 基準との差 |
|---|---|---|---|---|---|---|---|---|---|
| Thu | XAUUSD | CSV | -1.80 | 5 | 0 | -1.80 | 継続(あと 4 勝・残 5 月) |  | — |
| MonExHol | EURJPY | CSV | +0.22 | 3 | 1 | +0.22 | 継続(あと 3 勝・残 5 月) | Mon EURJPY | +0.19 |
| MonExHol | GBPJPY | CSV | +0.43 | 3 | 1 | +0.43 | 継続(あと 3 勝・残 5 月) | Mon GBPJPY | +0.02 |
| MonExHol | USDJPY | CSV | +1.06 | 3 | 1 | +1.06 | 継続(あと 3 勝・残 5 月) | Mon USDJPY | -0.21 |
| MonExHol | NZDJPY | CSV | +0.58 | 3 | 1 | +0.58 | 継続(あと 3 勝・残 5 月) | Mon NZDJPY | +0.28 |
| MonExHol | CHFJPY | CSV | -0.19 | 3 | 0 | -0.19 | 継続(あと 4 勝・残 5 月) | Mon CHFJPY | +0.29 |
| MonExAUNZ | AUDJPY | CSV | +0.40 | 2 | 1 | +0.40 | 継続(あと 3 勝・残 5 月) | Mon AUDJPY | -0.66 |
| MonExAUNZ | NZDJPY | CSV | +0.28 | 2 | 1 | +0.28 | 継続(あと 3 勝・残 5 月) | Mon NZDJPY | -0.02 |
| MonExJpTue | USDJPY | CSV | +1.26 | 4 | 1 | +1.26 | 継続(あと 3 勝・残 5 月) | Mon USDJPY | +0.00 |
| MonExJpTue | EURJPY | CSV | +0.03 | 4 | 1 | +0.03 | 継続(あと 3 勝・残 5 月) | Mon EURJPY | +0.00 |
| MonExJpTue | GBPJPY | CSV | +0.42 | 4 | 1 | +0.42 | 継続(あと 3 勝・残 5 月) | Mon GBPJPY | +0.00 |
| MonExJpTue | AUDJPY | CSV | +1.06 | 4 | 1 | +1.06 | 継続(あと 3 勝・残 5 月) | Mon AUDJPY | +0.00 |
| MonExJpTue | NZDJPY | CSV | +0.30 | 4 | 1 | +0.30 | 継続(あと 3 勝・残 5 月) | Mon NZDJPY | +0.00 |
| MonExJpTue | CADJPY | CSV | +1.09 | 4 | 1 | +1.09 | 継続(あと 3 勝・残 5 月) | Mon CADJPY | +0.00 |
| MonExJpTue | CHFJPY | CSV | -0.48 | 4 | 0 | -0.48 | 継続(あと 4 勝・残 5 月) | Mon CHFJPY | +0.00 |
| MonExGotobi | Mon7 | CSV | +0.54 | 3 | 1 | +0.54 | 継続(あと 3 勝・残 5 月) |  | — |
| HoldSL10 | BTCUSD | 再計算 | -7.37 | 31 | 0 | -7.37 | 継続(あと 4 勝・残 5 月) | Hold BTCUSD | +0.28 |
| MonIdxIntra | US30 | 再計算 | +0.69 | 4 | 1 | +0.69 | 継続(あと 3 勝・残 5 月) | Mon US30 | — |
| MonIdxIntra | JP225 | 再計算 | -0.63 | 4 | 0 | -0.63 | 継続(あと 4 勝・残 5 月) | Mon JP225 | -1.82 |
| MonJpyIntra6J | USDJPY | 再計算 | +0.66 | 4 | 1 | +0.66 | 継続(あと 3 勝・残 5 月) | Mon USDJPY | -0.61 |
| MonIdxSession0 | US500 | 再計算 | +0.79 | 4 | 1 | +0.79 | 継続(あと 3 勝・残 5 月) | Mon US500 | -0.31 |
| MonIdxSession0 | NAS100 | 再計算 | +0.66 | 4 | 1 | +0.66 | 継続(あと 3 勝・残 5 月) | Mon NAS100 | -0.72 |
| MonIdxSession0 | US30 | 再計算 | -0.01 | 4 | 0 | -0.01 | 継続(あと 4 勝・残 5 月) | Mon US30 | — |
| MonJpySession6J | USDJPY | 再計算 | +0.96 | 4 | 1 | +0.96 | 継続(あと 3 勝・残 5 月) | Mon USDJPY | -0.30 |
| RollGateB2 | Roll5 | 再計算 | +0.07 | 4 | 1 | +0.07 | 継続(あと 3 勝・残 5 月) |  | — |

- 25 本中 **19 本が 10 月 +**、棄却確定 0(1 か月では確定しない)。負は Thu XAUUSD・CHFJPY 系 2 本・HoldSL10 BTCUSD・MonIdxIntra JP225・MonIdxSession0 US30 の 6 本。
- 月曜派生(祝日・AU/NZ・火曜祝日・五十日の除外)は元の Mon と同符号で、差は除外が当たった週の分だけ(MonExAUNZ AUDJPY −0.66 は 10/26 NZ 労働者の日を除外した結果)。
- 時間足系: 日中版・セッション版は 10 月 +0.66〜+0.96% で、同月の Mon(24h)より 0.3〜0.7pt 小さい(持ち越しの分を取っていない)。RollGateB2 は +0.07%(10 月の Roll 4 本に対し門は非拘束)。
- HoldSL10 BTCUSD −7.37% は Hold BTCUSD −7.65% より +0.28pt(10 月は SL ヒットなし・差は窓の建て直しコストと経路の違い)。

## 4. 提案

| 項目 | 判定 | 理由 |
|---|---|---|
| 判定規則(docs/229 §4) | **変更しない** | 事前登録どおり 2027-03 末で確定 |
| 月初の定例 | 変更不要(自動) | `paper_forward.py` が本スクリプトを呼ぶ。Dukascopy が落ちている月は「未取得の月次 H1」を表示して日足系だけで続行し、翌月に追い付く |
| 月次改正案(docs/389 様式) | 「候補セル」行に `candidate_interim_latest.csv` の状態列を転記する | 判定は 2027-04 の改正案で |
| 11 月の EA 改訂 | 変更なし | 候補は紙上のみ(配備の変更は LEAD 確定・「切替」の後) |

## 5. 累積

- セル 0(工学)。累積 10,060(閾値不変)。
