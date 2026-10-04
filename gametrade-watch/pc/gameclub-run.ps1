# Entry point for the scheduled task "gameclub_watch": update gameclub-relay.ps1 from GitHub, then run it.
# Fixes pushed to the repository reach the PC without reinstalling. If GitHub can't be reached, the local copy runs.
# Keep this file ASCII only: Windows PowerShell 5.1 misreads UTF-8 without BOM.

$dir = $PSScriptRoot
$local = Join-Path $dir "gameclub-relay.ps1"
$new = Join-Path $dir "gameclub-relay.new.ps1"
Remove-Item $new -ErrorAction SilentlyContinue
curl.exe -sSf --connect-timeout 20 --retry 2 --retry-all-errors -o $new "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch/pc/gameclub-relay.ps1?v=$(Get-Date -Format yyyyMMddHHmmss)"
if ($LASTEXITCODE -eq 0 -and (Test-Path $new) -and (Select-String -Path $new -Pattern "GameClub \(gameclub.jp\) relay" -Quiet)) {
  Move-Item -Force $new $local
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $local
exit $LASTEXITCODE
