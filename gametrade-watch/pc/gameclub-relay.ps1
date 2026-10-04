# GameClub (gameclub.jp) relay: fetch the listing pages and send them to the Cloudflare Worker (src/worker.js).
# GameClub shows a bot-check page to cloud servers, so this runs on the home PC every night.
# The Worker does the matching, the Discord notification and keeps the state. Installed by pc/install-gameclub.ps1.
#
#   powershell -ExecutionPolicy Bypass -File gameclub-relay.ps1
#
# The token is read from token.txt in the same folder (never committed). Log: relay.log in the same folder.
# Keep this file ASCII only: Windows PowerShell 5.1 misreads UTF-8 without BOM.

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$log = Join-Path $dir "relay.log"
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Tee-Object -FilePath $log -Append }

try {
  $token = (Get-Content (Join-Path $dir "token.txt") -Raw).Trim()
  # The listing URL (price range) comes from config.gameclub.json on GitHub, so changing the range needs no reinstall.
  # ?v= avoids GitHub's cache. Falls back to the built-in URL if GitHub can't be reached.
  $base = "https://gameclub.jp/genshin-impact?search%5Btype%5D%5B1%5D=1&search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000"
  $maxPages = 10
  try {
    $cfgText = curl.exe -sSf "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch/config.gameclub.json?v=$(Get-Date -Format yyyyMMddHHmmss)"
    if ($LASTEXITCODE -eq 0) {
      $cfg = ($cfgText -join "`n") | ConvertFrom-Json
      if ($cfg.url) { $base = [string]$cfg.url }
      if ($cfg.pages) { $maxPages = [int]$cfg.pages }
    }
  } catch {}
  $ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
  $pages = @()
  for ($p = 1; $p -le $maxPages; $p++) {
    $f = Join-Path $env:TEMP "gameclub_p$p.html"
    $code = curl.exe -s -A $ua -o $f -w "%{http_code}" "$base&page=$p"
    if ($code -ne "200") { throw "page ${p}: HTTP $code" }
    # ReadAllText gives a plain string. Get-Content adds PSPath etc., which PowerShell 5.1's ConvertTo-Json
    # would send as an object instead of a string (the Worker then answers 400).
    $html = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
    if ($html -match "Just a moment") { throw "page ${p}: got the bot-check page" }
    $pages += $html
    if ($html -notmatch 'class="pager-next"') { break }  # last page
    Start-Sleep -Seconds 3
  }
  $body = @{ site = "gameclub"; pages = $pages } | ConvertTo-Json -Compress
  # Send with curl.exe from a UTF-8 (no BOM) file so the Worker's answer is always visible, even on errors.
  $bodyFile = Join-Path $env:TEMP "gameclub_body.json"
  [System.IO.File]::WriteAllText($bodyFile, $body, (New-Object System.Text.UTF8Encoding($false)))
  $resFile = Join-Path $env:TEMP "gameclub_res.json"
  $code = curl.exe -s -o $resFile -w "%{http_code}" -X POST "https://gametrade-watch.iq87jun.workers.dev/ingest" `
    -H "authorization: Bearer $token" -H "content-type: application/json; charset=utf-8" --data-binary "@$bodyFile"
  $res = [System.IO.File]::ReadAllText($resFile, [System.Text.Encoding]::UTF8)
  if ($code -ne "200") { throw "worker HTTP ${code}: $res" }
  Log "ok pages=$($pages.Count) $res"
} catch {
  Log "error $($_.Exception.Message)"
  exit 1
}
