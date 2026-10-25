# theoption プローブの実行ラッパー(タスクから呼ばれる)。毎回 GitHub から最新の to_probe.py / to_summarize.py を取り直してから実行する。
#   取得に失敗したら手元の版で続行。記録先は to_config.json の out(Drive の chien_ops\theoption)。
param([string]$Mode = "monday")   # monday / thursday = 09:30 JST まで記録、check = 60 秒
$here = Split-Path -Parent $MyInvocation.MyCommand.Path; Set-Location $here
$raw = "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/ccr-dbb29a98-7cflzp/ops/theoption"
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'
# v1.0a: run.log は 1 行ずつ共有モード(ReadWrite)で開いて追記する。Out-File -Append は実行中ずっと排他で開くため、
#   monday(05:25〜09:30)や tenbai(月07:05〜翌06:10)の最中に起動した live_* の出力が書けず、Python ごと止まっていた(10/26 07:00 の発注が未実行)。
#   開けなければ run_<Mode>.log へ。ログが書けなくても本体は止めない。
function Log([string]$s) {
  foreach ($p in @((Join-Path $here "run.log"), (Join-Path $here "run_$Mode.log"))) {
    for ($i = 0; $i -lt 5; $i++) {
      try { $fs = [IO.File]::Open($p, 'Append', 'Write', 'ReadWrite'); $sw = New-Object IO.StreamWriter($fs, (New-Object Text.UTF8Encoding($false))); $sw.WriteLine($s); $sw.Close(); return }
      catch { Start-Sleep -Milliseconds 200 }
    }
  }
}
foreach ($f in 'to_probe.py','to_summarize.py','to_setup.ps1','to_run.ps1','to_tenbai.py','to_live.py') {   # v0.9: 転売記録 / v1.0: 本番メニュー自動発注 も更新   # v0.4: 自分自身も取り直す(PS は起動時に全体を読み込むので実行中の上書きは次回から効く)
  try { Invoke-WebRequest ("$raw/$f" + "?t=" + (Get-Date).Ticks) -OutFile (Join-Path $here ($f + ".new")) -UseBasicParsing -TimeoutSec 60; Move-Item -Force (Join-Path $here ($f + ".new")) (Join-Path $here $f) }
  catch { Log "$(Get-Date -Format s) update failed $f : $_" }
}
$cfg = Get-Content (Join-Path $here "to_config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Mode -eq "mtlogsync") {   # v0.6: MT5共有FilesのEAログ(ChienMT_log_*.csv)をDrive同期フォルダへ冪等コピーして終了
  $src = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files"
  Get-ChildItem -Path $src -Filter "ChienMT_log_*.csv" -ErrorAction SilentlyContinue | Copy-Item -Destination $cfg.out -Force
  Log "$(Get-Date -Format s) mtlogsync done"
  exit 0
}
$env:THEOPTION_OUT = $cfg.out; $env:PYTHONUTF8 = "1"
if ($Mode -eq "live" -or $Mode -eq "live_settle" -or $Mode -eq "live_plan") {   # v1.0: 本番メニュー(追補18)の自動発注。既定はお試し口座(to_config.json の live_real=true + THEOPTION_API_KEY_REAL で実口座)
  if (-not $env:THEOPTION_API_KEY) { $env:THEOPTION_API_KEY = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User") }
  if (-not $env:THEOPTION_API_KEY_REAL) { $env:THEOPTION_API_KEY_REAL = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY_REAL", "User") }
  $a4 = @(if ($Mode -eq "live_settle") { "--settle" } elseif ($Mode -eq "live_plan") { "--plan" } else { "--out" })
  if ($Mode -eq "live") { & python (Join-Path $here "to_live.py") 2>&1 | ForEach-Object { Log "$_" } }
  else { & python (Join-Path $here "to_live.py") @a4 2>&1 | ForEach-Object { Log "$_" } }
  Log "$(Get-Date -Format s) mode=$Mode exit=$LASTEXITCODE"
  exit 0
}
if ($Mode -eq "tenbai" -or $Mode -eq "tenbai_once") {   # v0.9: 月曜 07:00 に ¥1,000×3 本を置き、転売情報を翌06:10まで30分ごとに記録、翌03:00 に 1 本転売(お試し口座)
  if (-not $env:THEOPTION_API_KEY) { $env:THEOPTION_API_KEY = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User") }
  $a3 = @(if ($Mode -eq "tenbai_once") { "--once" } else { "--live-demo" })   # PS 5.1 の 1 要素配列対策で @() で包む。tenbai = 発注+転売の実測(お試し口座)
  & python (Join-Path $here "to_tenbai.py") @a3 2>&1 | ForEach-Object { Log "$_" }
  Log "$(Get-Date -Format s) mode=$Mode exit=$LASTEXITCODE"
  exit 0
}
if (-not $env:THEOPTION_API_KEY) { $env:THEOPTION_API_KEY = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User") }
$args2 = @(if ($Mode -eq "check") { "--check" } else { "--until", "09:30" })   # @() で包む: PS 5.1 は 1 要素配列を文字列に崩し、@args2 が 1 文字ずつに展開される
& python (Join-Path $here "to_probe.py") @args2 2>&1 | ForEach-Object { Log "$_" }
Log "$(Get-Date -Format s) mode=$Mode exit=$LASTEXITCODE"
