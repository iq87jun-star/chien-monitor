# theoption プローブの実行ラッパー(タスクから呼ばれる)。毎回 GitHub から最新の to_probe.py / to_summarize.py を取り直してから実行する。
#   取得に失敗したら手元の版で続行。記録先は to_config.json の out(Drive の chien_ops\theoption)。
param([string]$Mode = "monday")   # monday / thursday = 09:30 JST まで記録、check = 60 秒
$here = Split-Path -Parent $MyInvocation.MyCommand.Path; Set-Location $here
$raw = "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/ccr-dbb29a98-7cflzp/ops/theoption"
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'
foreach ($f in 'to_probe.py','to_summarize.py','to_setup.ps1','to_run.ps1') {   # v0.4: 自分自身も取り直す(PS は起動時に全体を読み込むので実行中の上書きは次回から効く)
  try { Invoke-WebRequest ("$raw/$f" + "?t=" + (Get-Date).Ticks) -OutFile (Join-Path $here ($f + ".new")) -UseBasicParsing -TimeoutSec 60; Move-Item -Force (Join-Path $here ($f + ".new")) (Join-Path $here $f) }
  catch { Add-Content -Encoding UTF8 (Join-Path $here "run.log") "$(Get-Date -Format s) update failed $f : $_" }
}
$cfg = Get-Content (Join-Path $here "to_config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$env:THEOPTION_OUT = $cfg.out; $env:PYTHONUTF8 = "1"
if (-not $env:THEOPTION_API_KEY) { $env:THEOPTION_API_KEY = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User") }
$args2 = @(if ($Mode -eq "check") { "--check" } else { "--until", "09:30" })   # @() で包む: PS 5.1 は 1 要素配列を文字列に崩し、@args2 が 1 文字ずつに展開される
& python (Join-Path $here "to_probe.py") @args2 2>&1 | Out-File -Append -Encoding utf8 (Join-Path $here "run.log")
Add-Content -Encoding UTF8 (Join-Path $here "run.log") "$(Get-Date -Format s) mode=$Mode exit=$LASTEXITCODE"
