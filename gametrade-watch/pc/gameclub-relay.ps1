# GameClub (gameclub.jp) relay: fetch the listing pages and send them to the Cloudflare Worker (src/worker.js).
# GameClub shows a bot-check page to cloud servers, so this runs on the home PC every night.
# The Worker does the matching, the Discord notification and keeps the state.
# The scheduled task runs pc/gameclub-run.ps1, which first updates this file from GitHub.
#
# The token is read from token.txt in the same folder (never committed). Log: relay.log in the same folder.
# Errors are also reported to the Worker (shown at /status?site=gameclub as lastPcError).
# Keep this file ASCII only: Windows PowerShell 5.1 misreads UTF-8 without BOM.

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$log = Join-Path $dir "relay.log"
$worker = "https://gametrade-watch.iq87jun.workers.dev"
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Tee-Object -FilePath $log -Append }

# (--stderr instead of 2> : in PowerShell 5.1 a 2> redirect of a native command stops the script under "Stop".)
# POST a file to the Worker with retries (the network can drop for a moment). Returns @(httpCode, responseText, curlError).
function Send($bodyFile) {
  $resFile = Join-Path $env:TEMP "gameclub_res.json"
  $errFile = Join-Path $env:TEMP "gameclub_err.txt"
  Remove-Item $resFile, $errFile -ErrorAction SilentlyContinue
  $code = curl.exe -sS --connect-timeout 20 --max-time 120 --retry 3 --retry-delay 20 --retry-all-errors `
    -o $resFile -w "%{http_code}" -X POST "$worker/ingest" `
    -H "authorization: Bearer $token" -H "content-type: application/json; charset=utf-8" --data-binary "@$bodyFile" --stderr $errFile
  $res = if (Test-Path $resFile) { [System.IO.File]::ReadAllText($resFile, [System.Text.Encoding]::UTF8) } else { "" }
  $err = if (Test-Path $errFile) { ([System.IO.File]::ReadAllText($errFile)).Trim() } else { "" }
  return @($code, $res, "curl exit $LASTEXITCODE $err")
}

function WriteJson($obj, $name) {
  $f = Join-Path $env:TEMP $name
  [System.IO.File]::WriteAllText($f, ($obj | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
  return $f
}

$token = (Get-Content (Join-Path $dir "token.txt") -Raw).Trim()
try {
  # The listing URL (price range) comes from config.gameclub.json on GitHub, so changing the range needs no reinstall.
  # ?v= avoids GitHub's cache. Falls back to the built-in URL if GitHub can't be reached.
  $base = "https://gameclub.jp/genshin-impact?search%5Btype%5D%5B1%5D=1&search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000"
  $maxPages = 10
  try {
    $cfgText = curl.exe -sSf --connect-timeout 20 --retry 2 --retry-all-errors "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch/config.gameclub.json?v=$(Get-Date -Format yyyyMMddHHmmss)"
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
    Remove-Item $f -ErrorAction SilentlyContinue
    $code = curl.exe -s --connect-timeout 20 --max-time 60 --retry 3 --retry-delay 15 --retry-all-errors -A $ua -o $f -w "%{http_code}" "$base&page=$p"
    if ($code -ne "200") { throw "page ${p}: HTTP $code (curl exit $LASTEXITCODE)" }
    # ReadAllText gives a plain string. Get-Content adds PSPath etc., which PowerShell 5.1's ConvertTo-Json
    # would send as an object instead of a string (the Worker then answers 400).
    $html = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
    if ($html -match "Just a moment") { throw "page ${p}: got the bot-check page" }
    $pages += $html
    if ($html -notmatch 'class="pager-next"') { break }  # last page
    Start-Sleep -Seconds 3
  }
  $r = Send (WriteJson @{ site = "gameclub"; pages = $pages } "gameclub_body.json")
  if ($r[0] -ne "200") { throw "worker HTTP $($r[0]) ($($r[2])): $($r[1])" }
  Log "ok pages=$($pages.Count) $($r[1])"
} catch {
  $msg = $_.Exception.Message
  Log "error $msg"
  # Tell the Worker too, so the problem is visible without looking at this PC.
  try { [void](Send (WriteJson @{ site = "gameclub"; error = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" } "gameclub_error.json")) } catch {}
  exit 1
}
