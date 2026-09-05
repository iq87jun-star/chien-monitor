# 213.【手順書】Dukascopy H1・ティック取得を Cowork(ローカル)で実行する

> 2026-09-05。docs/209 で日足は本セッション(サンドボックス)から取得できたが、H1 とティックはリクエスト数が桁で多く
> サンドボックスのレート制限(503)では非現実的。**同じスクリプトをローカルで走らせる**だけで良い。
> 取得後に何を検定するかは §4。取得物の扱い(何をコミットするか)は §3。

## 1. 準備(1 回だけ)

```bash
git clone <このリポジトリ> && cd chien-monitor
git checkout claude/prop-trading-new-methods-a8y3l1
python3 -m pip install pandas numpy          # 標準ライブラリ以外はこれだけ(lzma は標準)
python3 research/tools/dukascopy_fetch.py --probe   # 疎通確認: "probe: ... OK" と "probe day XAUUSD 2024: 2xx 本" が出れば可
```

ローカル回線は 503 が出にくいので、`research/tools/dukascopy_fetch.py` 先頭の `REQ_SLEEP = 2.0` を `1.0` に下げて良い(0.5 未満は非推奨)。

## 2. 取得(優先順・合計約 4,300 リクエスト・REQ_SLEEP=1.0 で 1.5〜2 時間)

| 優先 | 目的 | コマンド | 目安 |
|---|---|---|---|
| A | docs/210 §5.3 の H1 再検証(ECB 前日 GER40・FOMC 当日 EURUSD・対照 US500) | `python3 research/tools/dukascopy_fetch.py --tf hour --syms GER40,EURUSD,US500 --from 2003-01-01` | 約 710 月ファイル |
| B | docs/208 日中フェーズ2(Mon FX ペアの 4/6/8/10 UTC 窓・v9 12h) | `python3 research/tools/dukascopy_fetch.py --tf hour --syms GBPJPY,AUDJPY,USDJPY,EURJPY,GBPUSD,USDCHF,NZDUSD,AUDUSD --from 2016-01-01` | 約 1,020 |
| C | B-2 の代替: 時間帯別スプレッド実測(2026 年 8 月・1 ヶ月) | `python3 research/tools/dukascopy_fetch.py --tf tick --syms GBPJPY,USDJPY,AUDJPY,EURJPY,GBPUSD --from 2026-08-01 --to 2026-08-31` | 約 2,500(週末は即 404) |

- 途中で止まっても再実行すれば未取得分から再開する。`!! FetchError` が出た銘柄は再実行。
- 2026 年分: 日足の年ファイルは 2025-12 で止まっているが(docs/209)、H1 の月ファイルとティックの日ファイルは 2026 年も存在するはず。
  A/B の出力末尾が 2026-08 まで届いているか `tail -1 research/data_dukascopy/EURUSD_hour.csv` で確認する。

## 3. 取得後にコミットするもの(生ティックはコミットしない)

```bash
# H1 は gzip でコミット(1 本 5〜10MB → 1〜2MB)
cd research/data_dukascopy && for f in *_hour.csv; do gzip -kf "$f"; done && cd ../..
git add -f research/data_dukascopy/*_hour.csv.gz
# ティックは要約だけ
python3 research/tools/tick_spread_profile.py GBPJPY USDJPY AUDJPY EURJPY GBPUSD
git add research/results/spread_profile_*.csv
git commit -m "Dukascopy H1(A/B)+スプレッド・プロファイル(C) を Cowork で取得(docs/213)"
git push -u origin claude/prop-trading-new-methods-a8y3l1
```

## 4. 取得後に走る検定(このセッション側で実施・事前登録は別 doc)

1. **ECB 前日 GER40・24h 窓**(G3 型: 前日 12:45 GMT → 当日 12:40 GMT)と **FOMC 当日 EURUSD 24h 窓**。docs/210 §5.3 の「次回一次」。
2. **docs/208 フェーズ2**: 配備中の 4/6/8/10 UTC 窓を Dukascopy H1 で再現(Yahoo H1 は 2 年しか無い)。v9 12h LEAD の 10 年検定。
3. **コスト側(新境地 4)**: 時間帯別スプレッド曲線を `recentfit_screen` のコスト定数(2×pip 固定)と突き合わせ、
   Mon レグの建玉時刻(月曜 00:00 GMT 付近=スプレッド最悪帯)の実効コストで選抜スコアを再計算する。
