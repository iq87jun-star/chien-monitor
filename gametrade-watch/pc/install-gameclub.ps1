# Install the GameClub new-listing notifier on the home PC (run once; running again updates it).
#   1. Download gameclub-run.ps1 and gameclub-relay.ps1 from GitHub into C:\chien\gameclub
#   2. Save the token to token.txt (-Token)
#   3. Register the daily task "gameclub_watch" at 22:40 (runs after wake-up if the PC was asleep)
#   4. Run it once and show the result
#
#   powershell -ExecutionPolicy Bypass -File install-gameclub.ps1 -Token <token>
#
# Keep this file ASCII only: Windows PowerShell 5.1 misreads UTF-8 without BOM.

param([Parameter(Mandatory = $true)][string]$Token, [string]$At = "22:40")

$ErrorActionPreference = "Stop"
$dir = "C:\chien\gameclub"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
# ?v= avoids an old copy from GitHub's cache (it keeps files for about 5 minutes)
foreach ($name in "gameclub-run.ps1", "gameclub-relay.ps1") {
  curl.exe -sSf -o (Join-Path $dir $name) "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch/pc/$($name)?v=$(Get-Date -Format yyyyMMddHHmmss)"
  if ($LASTEXITCODE -ne 0) { throw "could not download $name" }
}
# The task runs gameclub-run.ps1, which updates gameclub-relay.ps1 from GitHub on every run.
$script = Join-Path $dir "gameclub-run.ps1"
Set-Content -Path (Join-Path $dir "token.txt") -Value $Token -NoNewline -Encoding ASCII

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "gameclub_watch" -Action $action -Trigger $trigger -Settings $settings `
  -Description "GameClub new listings to Discord (chien-monitor/gametrade-watch)" -Force | Out-Null
Write-Host "Registered task gameclub_watch (daily at $At). Running it once..."

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script
Get-Content (Join-Path $dir "relay.log") -Tail 1
