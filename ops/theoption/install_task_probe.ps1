# theoption プローブを Windows タスクスケジューラに登録する(VPS は JST)。取引はしない。
#   月曜 05:25 JST 起動 → 09:30 JST まで記録(開場 夏 06:00 / 冬 07:00 の前後を両方カバー)
# 先に「ユーザー環境変数」THEOPTION_API_KEY にお試し用キーを入れておく:
#   [Environment]::SetEnvironmentVariable("THEOPTION_API_KEY", "<キー>", "User")   ← この行は自分の PC の PowerShell でだけ打つ
# 実行: powershell -ExecutionPolicy Bypass -File install_task_probe.ps1
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = "C:\Program Files\Python312\python.exe" }
if (-not [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User")) { Write-Host "THEOPTION_API_KEY(ユーザー環境変数)が無い。先に設定"; exit 1 }
$script   = Join-Path $here "to_probe.py"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 5) -MultipleInstances IgnoreNew
$action   = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --until 09:30" -WorkingDirectory $here
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "05:25"
Register-ScheduledTask -TaskName "chien_theoption_probe_Monday" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "登録: chien_theoption_probe_Monday  月曜 05:25 → 09:30 JST / 記録は out\probe_demo_*.jsonl / 要約: python to_summarize.py <ファイル>"
