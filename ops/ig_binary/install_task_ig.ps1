# chien IG 窓埋めボットを Windows タスクスケジューラに登録する(VPS は JST)。
#   signal: 月曜 07:02 JST(07:00 の値が出揃ってから)/ settle: 月曜 09:05 JST / report: 日曜 12:00 JST(週次の集計を log に出すだけ)
# 実行: powershell -ExecutionPolicy Bypass -File install_task_ig.ps1   (config.json を先に用意。transport=dry のまま登録すれば通知は印字のみ)
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "C:\Program Files\Python312\python.exe" }
$script = Join-Path $here "ig_gap_bot.py"; $config = Join-Path $here "config.json"
if (-not (Test-Path $config)) { Write-Host "config.json が無い。config.example.json をコピーして編集してから実行"; exit 1 }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
foreach ($t in @(@("signal","Monday","07:02"), @("settle","Monday","09:05"), @("report","Sunday","12:00"))) {
  $action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --config `"$config`" --action $($t[0])" -WorkingDirectory $here
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t[1] -At $t[2]
  Register-ScheduledTask -TaskName "chien_ig_$($t[0])_$($t[1])" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "登録: chien_ig_$($t[0])_$($t[1])  $($t[1]) $($t[2]) JST"
}
Write-Host "状態確認: python ig_gap_bot.py --config config.json --action status / 停止: HALT という空ファイルを置く(通知しなくなる)"
