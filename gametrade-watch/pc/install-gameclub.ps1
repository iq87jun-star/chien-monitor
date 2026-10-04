# ゲームクラブ新着通知を自宅の PC に登録する(1回だけ実行)。
#   1. C:\chien\gameclub に gameclub-relay.ps1 を GitHub から取得
#   2. 合言葉を token.txt に保存(引数 -Token)
#   3. 毎日 22:40 に実行するタスク「gameclub_watch」を登録(PC がその時刻に寝ていたら起動後に実行)
#   4. 1回実行して結果を表示
#
#   powershell -ExecutionPolicy Bypass -File install-gameclub.ps1 -Token <合言葉>

param([Parameter(Mandatory = $true)][string]$Token, [string]$At = "22:40")

$ErrorActionPreference = "Stop"
$dir = "C:\chien\gameclub"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$script = Join-Path $dir "gameclub-relay.ps1"
curl.exe -sSf -o $script "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch/pc/gameclub-relay.ps1"
if ($LASTEXITCODE -ne 0) { throw "gameclub-relay.ps1 を取得できませんでした" }
Set-Content -Path (Join-Path $dir "token.txt") -Value $Token -NoNewline -Encoding ASCII

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "gameclub_watch" -Action $action -Trigger $trigger -Settings $settings `
  -Description "ゲームクラブの新着を Discord に通知(chien-monitor/gametrade-watch)" -Force | Out-Null
Write-Host "タスク gameclub_watch を登録しました(毎日 $At)。1回実行します..."

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script
Get-Content (Join-Path $dir "relay.log") -Tail 1
