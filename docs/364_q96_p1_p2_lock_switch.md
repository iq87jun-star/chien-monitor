# 364.【Q96・設計】P1 通過 → P2 のロック自動切替 — 推奨は「manifest の段階切替(チャートの EA 入力で P2 値を注入)」+ EA 側は「基準残高の照合ガード」だけ

2026-10-20(docs/322 の改正プログラム・order 13・セル 0・設計書のみ)。実装は 11/1 の EA 改訂(agent 1.9・manifest v3)で。配備・EA・manifest は本書では変更しない。

## 0. 結論
| | A. EA 側で自動検知 | **B. manifest の段階切替(推奨)** | C. 現状(人手で `InpLock*` を変えて再配備) |
|---|---|---|---|
| 検知 | 口座番号変更 or 残高リセットを OnInit で推定 | **人が新ログインを `terminals.json` に足す**(秘密は VPS 内のみ)。段階は manifest の `phase` で宣言 | 人が全部 |
| 誤検知の損失 | 高(§2: 基準残高のずれ事故 docs/241 §69 と同型) | **低**(宣言した値しか入らない) | 中(入力を手で打ち間違える) |
| 人手 | 0〜1 手順 | **2 手順**(ログイン追記・manifest 1 行) | 4〜6 手順 |
| EA 変更 | 大(段階表・永続化・判定) | **小**(`InpExpectedInitBal` の照合ガードのみ・v+0.01) | 無し |
| 通過後〜P2 開始の空白 | 無し | 1 時間以内(毎時タスク) | 数時間〜1 日 |
| 業者差への耐性 | 業者ごとに判定が要る | 宣言なので業者差は manifest に閉じる | — |

**B を採る。** 根拠は §2(EA が「今が P2 か」を安全に知る手段が無い)と §3(配備側は既に口座 = ログイン単位で動いており、`<inputs>` を書く口だけ足せば済む)。A の要素は「基準残高の照合」だけ EA に残す(§4.3)。

## 1. 現状の仕組み(読み合わせ)
- ロックは EA の 3 入力: `InpLockArmPct`(新規停止)/ `InpLockClosePct`(全決済・恒久ロック `PASS_LOCK`)/ `InpProfitStopPct`(保険)。P1 の値は FTMO 10%(9.9 / 10.05 / 10.1)、FN Stellar 8%(7.9 / 8.05 / 8.1)、Fintokei スイング 8%。P2 は FTMO 5%(4.9 / 5.05 / 5.1)、FN 5%、Fintokei 6%(docs/220)。
- 基準残高 `g_initBal` は `InpInitialBalance`(>0 なら固定)→ 端末の GlobalVariable `ChienRF_base_<login>_<MagicBase>`(復元)→ 初回アタッチ時の残高(新規記録)の順。`InpBaselineReset=true` で取り直し。
- `g_passLocked` はメモリだけ(永続化なし)。再起動後は gain が `InpLockClosePct` 以上なら毎 tick 再ロックするので実害はないが、**P2 の新ログインで同じ入力のまま起動すると gain=0 から P1 の 10% を目標に取引を続ける**(= 現状の人手切替が必要な理由)。
- 段階の移行は業者により **新ログイン**(FTMO: Challenge → Verification → FTMO Account、FN Stellar 2-step: P1 → P2 → Funded はいずれも別口座番号)。同一ログインで残高だけリセットされる業者は現保有には無い(Fintokei スイングは要確認・docs/220 に記載なし)。
- 配備(`chien_deploy.py`)は口座 = ログイン単位: `terminals.json` の端末にログインし、manifest `accounts[<login>]` の `ensure` に従いチャート `chart01.chr` の `<expert>` を書く。`expert_block()` は `<inputs></inputs>` を**空で**書く(= EA は既定値で起動)。`parse_chart()` は `<inputs>` を読める。
- 事故の前例(docs/241 §69): #531343523 で端末変更時に GlobalVariable が無く基準残高が 96,444 に取り直され、+8.05% ロックが実際の +4.2% で発火した。**基準残高の誤りはロックの誤発火・不発の両方を生む**。段階切替の設計はここを最優先で守る。

## 2. A 案(EA 側で自動検知)を採らない理由
1. **段階を知る手段が無い**: 新ログインでは GlobalVariable の名前空間(login)が変わるので「前段階で通過した」記憶が EA に残らない。同一端末の別 GV(`ChienRF_phase_<MagicBase>`)に段階を残す案は、1 端末 = 1 口座の現運用では成立するが、端末を作り直した・バックアップから戻した・別口座を同じ端末で開いた、のいずれでも壊れる(§1 の前例と同じ壊れ方)。
2. **残高リセットの判定が業者依存**: 「残高が切りの良い初期値に戻った」は P2 開始とも、同一段階の再購入(リセット)とも、資金追加とも区別できない。誤って P2 値(5%)に下げると P1 で早すぎるロック(通過不能)、誤って P1 値に留まると P2 で目標超過後も取引を続ける(失格リスクを無償で負う)。
3. EA の変更量が大きく(段階表の入力・永続化・判定・ログ)、Q94 のパリティ試験で「取引ロジック不変」を示しにくい。

## 3. B 案(manifest の段階切替)の設計
### 3.1 manifest v3 のスキーマ追加(`ops/config/deploy_manifest.json`)
```json
"531407058": {
  "apply": true, "terminal": "FTMO",
  "phase": "P1",
  "ensure": [{"ea": "…EA3_Mon4_6.0倍_dyn1_v1.19.mq5", "symbol": "GBPJPY", "period": "H1",
              "inputs": {"InpLockArmPct": 9.9, "InpLockClosePct": 10.05, "InpProfitStopPct": 10.1,
                         "InpExpectedInitBal": 50000, "InpInitialBalance": 50000}}],
  "successor": {"phase": "P2", "inputs": {"InpLockArmPct": 4.9, "InpLockClosePct": 5.05, "InpProfitStopPct": 5.1,
                                          "InpExpectedInitBal": 50000, "InpInitialBalance": 50000, "InpBaselineReset": true}}
}
```
- `ensure[].inputs`: チャートの `<inputs>` に `Name=Value` で書く(既存の `expert_block()` に 1 引数足す)。**書かない入力は EA 既定値**のまま(現行と同じ)。
- `successor`: この口座が通過したあとに発行される**次段階の口座**に適用する入力。口座番号は発行まで不明なので、ここでは「P1 口座の後継」として持つ。
- `phase`: 表示と検査用(§3.3 の照合)。

### 3.2 agent 1.9 の手順(毎時・`--discover` の延長)
1. `terminals.json` に新しいログインが足されている(人手: FTMO/FN からメールで届く口座番号・パスワードを VPS 内で追記。公開リポジトリには出さない)。
2. agent は新ログインの端末に接続し、manifest に `accounts[<新login>]` が無ければ、**同じ `terminal` 文字列を持ち `phase` が 1 つ前で `[PROFIT LOCK]` をログに出している口座**を前任として探し、その `successor` を適用する(EA は同じファイル・`inputs` だけ successor の値)。
3. `deploy_status.json` に `phase_from: 531407058 → P2` と適用した `inputs` を書き、ダイジェスト(07:50)が「P2 自動適用・manifest に正式登録が必要」と報告する。私が manifest に `accounts[<新login>]`(`phase: "P2"`・`inputs` 明示)を追記して commit(= 以後は successor ではなく明示設定で動く)。
4. 前任口座(P1)は `[PROFIT LOCK]` 後も端末が動いていれば `apply:false` に落とす(建玉なし・取引なし)。
- 人手は「ログイン追記」の 1 手順だけ。残りは manifest の宣言と agent の照合で済む。

### 3.3 照合(誤適用を防ぐ 3 条件・1 つでも外れたら適用せず報告のみ)
| 条件 | 判定 | 外れたときの意味 |
|---|---|---|
| 残高 | 新ログインの `balance` が `successor.inputs.InpExpectedInitBal` の ±0.5% 以内 | 別サイズの口座・資金追加・P2 ではない |
| 前任 | 前任口座のログに `[PROFIT LOCK]` があり、その後 `[Mon ENTRY]` 等の新規建てが無い | まだ通過していない・別口座 |
| 業者 | 新ログインの `server`/`company` が前任と同じ | 端末の取り違え |

### 3.4 EA 側の最小変更(v+0.01・取引ロジック不変)
- 入力 `InpExpectedInitBal`(0=無効)を追加: OnInit で `g_initBal` 決定後、`|g_initBal − InpExpectedInitBal| / InpExpectedInitBal > 0.5%` なら **`INIT_FAILED` で止める**(ログ `[BASE MISMATCH] 基準 %.2f 期待 %.2f`・Notify)。docs/241 §69 の事故はこれで初期化時点で止まる。
- `g_passLocked` を GlobalVariable `ChienRF_lock_<login>_<MagicBase>` に永続化(通過後の再起動で「ロック済み」を確実に保つ。P2 の新ログインは名前空間が違うので影響しない)。
- 変更はこの 2 点のみ。`InpLock*` の意味・既定値・ロックの判定式は不変 → Q94 のパリティ試験は「入力既定値で v1.19 と同一の取引」を確認すれば足りる。

### 3.5 Funded(本番口座)への接続
通過後の Funded 口座も同じ機構で扱える: `successor` を 2 段(P2 → Funded)にし、Funded の `inputs` は `InpProfitLockEnable=false`・`InpDynK`/`InpKeepPct`(Q131)・倍率。Q86(docs/360)の「funded 口座 = 別ログイン → manifest の項目」はこの形に収まる。

## 4. 試験計画(11/1 改訂で実施・Q94 の tester と agent のドライラン)
1. `chien_deploy.py` 単体: `expert_block(inputs=…)` → `parse_chart()` で往復一致(ユニットテスト・入力の順序と小数の書式)。
2. agent `--dry-run`: `terminals.json` にダミーの新ログイン(デモ口座)を足し、manifest の `successor` が §3.3 の 3 条件で適用/不適用に分かれることを `deploy_status.json` で確認。
3. EA: `InpExpectedInitBal` を故意にずらして `INIT_FAILED` になること、合わせると `[INIT]` が出ること(tester でも可)。
4. 本番初回は FN 14166201(P1 残 +3.4%・docs/349 §8 の到達中央 10/30)で、P2 口座発行 → `terminals.json` 追記 → 翌時の agent で P2 入力が入ることを人が確認(`deploy_status.json` の `phase_from`)。

## 5. 提案(11 月の EA 改訂 / 新規口座への含意)
- **採用: B 案**。manifest v3(`ensure[].inputs`・`successor`・`phase`)+ agent 1.9(`--discover` 延長・§3.3 照合)+ EA v+0.01(`InpExpectedInitBal`・ロック永続化)。実装順: deploy の `<inputs>` 書き込み → EA 2 点 → agent の後継適用。
- 既存 10 口座は改訂時に `ensure[].inputs` に現在の P1 値と `InpExpectedInitBal`(口座サイズ)を**明示**する(既定値依存をやめる)。これだけで §1 の事故型は再発しない。
- 新規口座(docs/320 の購入候補)は購入時から `successor` 込みで登録 → P1 通過から P2 開始まで人手 1 手順・空白 1 時間以内。
- 変更しないもの: ロックの値そのもの(P2 の最適値は Q105・P1 通過後)、Q85 の倍率フロンティア(P1→P2 切替時に適用する値は Q85 の表から入れる)。

累積セル数: 9,750(本項目はセル 0・加算なし)。
