# chien 運用エージェントを Windows タスクスケジューラに登録する(docs/317 段階 1・v2)
# 管理者権限は不要(現在のユーザーで登録): powershell -ExecutionPolicy Bypass -File install_task.ps1
# トリガー: (a) 毎時(日付 00:00 起点の 1 時間繰り返し) + (b) ログオン 3 分後から 1 時間繰り返し。
#   (b) があるので PC を起動すれば自動で再開する。電池駆動でも開始・継続(既定では AC 電源時のみ実行になり止まる)。
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe" }
$script = Join-Path $here "chien_ops_agent.py"
$config = Join-Path $here "terminals.json"
$log    = Join-Path $here "agent.log"
if (-not (Test-Path $config)) { Write-Host "terminals.json が無い。terminals.example.json をコピーして編集してから実行" ; exit 1 }
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$python`" `"$script`" --config `"$config`" >> `"$log`" 2>&1" -WorkingDirectory $here
$hourly  = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$logon   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logon.Delay = "PT3M"
$logon.Repetition = $hourly.Repetition
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "chien_ops_agent" -Action $action -Trigger @($hourly, $logon) -Settings $settings -Force | Out-Null
$t = Get-ScheduledTask -TaskName "chien_ops_agent"; $i = $t | Get-ScheduledTaskInfo
Write-Host "登録: chien_ops_agent(ログオン 3 分後 + 毎時・電池駆動でも実行)。状態=$($t.State) 次回=$($i.NextRunTime) 前回結果=$($i.LastTaskResult)"
Write-Host "手動実行: schtasks /run /tn chien_ops_agent  / ログ: $log  / 自己診断: Drive の chien_ops\_diag\"
