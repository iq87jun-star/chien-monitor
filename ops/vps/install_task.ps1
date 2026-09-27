# chien 運用エージェントを Windows タスクスケジューラに登録する(docs/317 段階 1)
# 管理者権限は不要(現在のユーザーで登録): powershell -ExecutionPolicy Bypass -File install_task.ps1
# 毎時 05 分に実行(equity スナップショットは毎時、約定・ログは毎回全量書き直し)。
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe" }
$script = Join-Path $here "chien_ops_agent.py"
$config = Join-Path $here "terminals.json"
$log    = Join-Path $here "agent.log"
if (-not (Test-Path $config)) { Write-Host "terminals.json が無い。terminals.example.json をコピーして編集してから実行" ; exit 1 }
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$python`" `"$script`" --config `"$config`" >> `"$log`" 2>&1" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "chien_ops_agent" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "登録: chien_ops_agent(毎時)。手動実行: schtasks /run /tn chien_ops_agent  / ログ: $log"
