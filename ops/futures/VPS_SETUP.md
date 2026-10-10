# 先物ボット(Q117・docs/336)の VPS 配置手順 — VPS 上の Claude セッション、または PowerShell で手動

前提: VPS(お名前.com・Windows)、Python 3.12(`C:\Program Files\Python312`)、`C:\chien`。秘密(TradersPost の Webhook URL)はユーザーが最後に `config.json` へ貼る。`ops/vps/terminals.json` は読まない・送らない。

## 1. ファイルを置く(`C:\chien\ops\futures\`)
リポジトリ iq87jun-star/chien-monitor・枝 `claude/prop-trading-new-methods-a8y3l1` から
`ops/futures/mffu_bot.py`・`config.example.json`・`install_task_futures.ps1`・`test_mffu_bot.py` と
`research/data_ext/holidays_us_uk_au_nz_2016_2027.csv` を取る。
- `C:\chien` が git 作業コピーなら: `cd C:\chien; git pull`
- そうでなければ以前 `chien_ops_agent.py` を取得したのと同じ方法(GitHub からの取得)で 5 ファイルを `C:\chien\ops\futures\` にコピーする。

## 2. config.json を作る(UTF-8)
```
cd C:\chien\ops\futures
New-Item -ItemType Directory "G:\マイドライブ\chien_ops\futures" -Force   # G: が無ければ省略
Copy-Item config.example.json config.json
```
`config.json` を編集(`notepad config.json`):
- `"transport": "dry"`(URL を貼った後に `"webhook"` へ)
- `"symbols": {"MES": {"qty": 6, "cfd": "US500"}, "MNQ": {"qty": 3, "cfd": "NAS100"}, "MYM": {"qty": 6, "cfd": "US30"}}`(Builder 150K・docs/336 §9)
- `"max_contracts_total": 15`
- `"holidays_csv": "C:\\chien\\ops\\futures\\holidays_us_uk_au_nz_2016_2027.csv"`
- `"log_csv": "G:\\マイドライブ\\chien_ops\\futures\\mffu_log.csv"`(G: が無ければ `"C:\\chien\\ops\\futures\\out\\mffu_log.csv"`)
- `"state_json": "C:\\chien\\ops\\futures\\out\\state.json"`
- `"webhook_url"`: ユーザーが TradersPost の戦略ページの URL を貼る(チャットに貼らない)

## 3. 検証(ネットワーク・発注なし)
```
cd C:\chien\ops\futures
python -c "import test_mffu_bot as T, inspect; [f() for n,f in inspect.getmembers(T, inspect.isfunction) if n.startswith('test_')]; print('tests ok')"
python mffu_bot.py --config config.json --action status
python mffu_bot.py --config config.json --action entry --date 2026-10-12 --dry
python mffu_bot.py --config config.json --action exit  --date 2026-10-12 --dry
Remove-Item out\state.json -ErrorAction SilentlyContinue   # dry の痕跡を消して初期状態に戻す
```
期待: `tests ok`、status に `transport=dry` と `MESZ2026 ×6 / MNQZ2026 ×3 / MYMZ2026 ×6`、entry/exit で `[dry]` 行が 3+3。

## 4. タスク登録(5 本・JST)
```
powershell -ExecutionPolicy Bypass -File install_task_futures.ps1
schtasks /query /tn chien_futures_entry_Monday /fo list | findstr /i "次回 Next"
```
entry 月 22:00 / exit 火 05:00 / check 火 05:30 / keepalive 火 22:00・木 22:00。

## 5. 本番化(ユーザー)
`notepad config.json` で `webhook_url` を貼り `transport` を `"webhook"` にして保存。CME 再開後(月曜 07:00 JST 以降)に
`python mffu_bot.py --config config.json --action test` を実行し、TradersPost の紙口座に MES 1 枚の買い→決済が出ることを確認してから、MFFU 口座(69207025)の Subscription を Enable。
停止したいとき: `C:\chien\ops\futures\HALT` という空ファイルを置く(建てなくなる・決済は続く)。
