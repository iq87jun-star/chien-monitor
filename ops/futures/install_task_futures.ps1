# chien 先物ボット(docs/336 Q117)を Windows タスクスケジューラに登録する。VPS は JST(夏時間なし)なので UTC 固定の時刻をそのまま JST に直す。
#   entry: 月曜 13:00 UTC = 月曜 22:00 JST / exit: 月曜 20:00 UTC = 火曜 05:00 JST / check: 20:30 UTC = 火曜 05:30 JST / keepalive: 火曜 13:00 UTC = 火曜 22:00 JST(休場週のみ動く)
# 実行: powershell -ExecutionPolicy Bypass -File install_task_futures.ps1   (config.json を先に用意。transport=dry のまま登録すれば発注は印字のみ)
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "C:\Program Files\Python312\python.exe" }
$script = Join-Path $here "mffu_bot.py"; $config = Join-Path $here "config.json"
if (-not (Test-Path $config)) { Write-Host "config.json が無い。config.example.json をコピーして編集してから実行"; exit 1 }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
foreach ($t in @(@("entry","Monday","22:00"), @("exit","Tuesday","05:00"), @("check","Tuesday","05:30"), @("keepalive","Tuesday","22:00"))) {
  $action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --config `"$config`" --action $($t[0])" -WorkingDirectory $here
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t[1] -At $t[2]
  Register-ScheduledTask -TaskName "chien_futures_$($t[0])" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "登録: chien_futures_$($t[0])  $($t[1]) $($t[2]) JST"
}
Write-Host "状態確認: python mffu_bot.py --config config.json --action status / 停止: HALT という空ファイルを置く(建てなくなる・決済は続く)"
