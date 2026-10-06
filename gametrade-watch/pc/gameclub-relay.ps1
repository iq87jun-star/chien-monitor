# GameClub (gameclub.jp) relay - also GameTrade (gametrade.jp): fetch the listing pages and send them to the
# Cloudflare Worker (src/worker.js). Both sites refuse cloud servers, so this runs on the home PC every night.
# The Worker does the matching, the Discord notification and keeps the state.
# The scheduled task runs pc/gameclub-run.ps1, which first updates this file from GitHub.
#
# The token is read from token.txt in the same folder (never committed). Log: relay.log in the same folder.
# Errors are also reported to the Worker (shown at /status?site=<site> as lastPcError).
# Keep this file ASCII only: Windows PowerShell 5.1 misreads UTF-8 without BOM.

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$log = Join-Path $dir "relay.log"
$worker = "https://gametrade-watch.iq87jun.workers.dev"
$raw = "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/main/gametrade-watch"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
# Write-Host, not the pipeline: inside a function, pipeline output would become part of its return value.
function Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  Add-Content -Path $log -Value $line -Encoding Unicode  # same as the existing log (Tee-Object in 5.1 wrote UTF-16)
  Write-Host $line
}

# (--stderr instead of 2> : in PowerShell 5.1 a 2> redirect of a native command stops the script under "Stop".)
# POST a file to the Worker with retries (the network can drop for a moment). Returns @(httpCode, responseText, curlError).
function Send($bodyFile) {
  $resFile = Join-Path $env:TEMP "gamewatch_res.json"
  $errFile = Join-Path $env:TEMP "gamewatch_err.txt"
  Remove-Item $resFile, $errFile -ErrorAction SilentlyContinue
  $code = curl.exe -sS --connect-timeout 20 --max-time 180 --retry 3 --retry-delay 20 --retry-all-errors `
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

# The listing URL (price range) and page count come from the site's config on GitHub, so changing them needs
# no reinstall. ?v= avoids GitHub's cache. Falls back to the built-in values if GitHub can't be reached.
function SiteConfig($file, $url, $pages) {
  try {
    $text = curl.exe -sSf --connect-timeout 20 --retry 2 --retry-all-errors "$raw/$($file)?v=$(Get-Date -Format yyyyMMddHHmmss)"
    if ($LASTEXITCODE -eq 0) {
      $cfg = ($text -join "`n") | ConvertFrom-Json
      if ($cfg.url) { $url = [string]$cfg.url }
      if ($cfg.pages) { $pages = [int]$cfg.pages }
    }
  } catch {}
  return @($url, $pages)
}

# Fetch up to $maxPages pages. $marker must appear in a real listing page. With $stopAtLast, stop at the page
# without a "next" link (GameClub filters the price range itself, so the range fits in a few pages).
function FetchPages($site, $base, $maxPages, $marker, $stopAtLast) {
  $pages = @()
  for ($p = 1; $p -le $maxPages; $p++) {
    $f = Join-Path $env:TEMP "$($site)_p$p.html"
    Remove-Item $f -ErrorAction SilentlyContinue
    $code = curl.exe -s --connect-timeout 20 --max-time 60 --retry 3 --retry-delay 15 --retry-all-errors -A $ua -H "accept-language: ja" -o $f -w "%{http_code}" "$base&page=$p"
    if ($code -ne "200") { throw "page ${p}: HTTP $code (curl exit $LASTEXITCODE)" }
    # ReadAllText gives a plain string. Get-Content adds PSPath etc., which PowerShell 5.1's ConvertTo-Json
    # would send as an object instead of a string (the Worker then answers 400).
    $html = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
    if ($html -match "Just a moment") { throw "page ${p}: got the bot-check page" }
    if ($html -notmatch $marker) { throw "page ${p}: no listings found (the page layout may have changed)" }
    $pages += $html
    if ($stopAtLast -and $html -notmatch 'class="pager-next"') { break }  # last page
    Start-Sleep -Seconds 3
  }
  return ,$pages
}

function RunSite($site, $cfgFile, $defaultUrl, $defaultPages, $marker, $stopAtLast) {
  try {
    $cfg = SiteConfig $cfgFile $defaultUrl $defaultPages
    $pages = FetchPages $site $cfg[0] $cfg[1] $marker $stopAtLast
    $r = Send (WriteJson @{ site = $site; pages = $pages } "$($site)_body.json")
    if ($r[0] -ne "200") { throw "worker HTTP $($r[0]) ($($r[2])): $($r[1])" }
    Log "$site ok pages=$($pages.Count) $($r[1])"
    return $true
  } catch {
    $msg = $_.Exception.Message
    Log "$site error $msg"
    # Tell the Worker too, so the problem is visible without looking at this PC.
    try { [void](Send (WriteJson @{ site = $site; error = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" } "$($site)_error.json")) } catch {}
    return $false
  }
}

$token = (Get-Content (Join-Path $dir "token.txt") -Raw).Trim()
$ok1 = RunSite "gameclub" "config.gameclub.json" `
  "https://gameclub.jp/genshin-impact?search%5Btype%5D%5B1%5D=1&search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000" `
  10 'class="item-row' $true
$ok2 = RunSite "gametrade" "config.json" `
  "https://gametrade.jp/genshin-impact/exhibits?5star-character=all&exclude_keyword=&filter=purchasable&genseki=all&high_price=200000&identity_verification=checked&keyword=&low_price=70000&rank=all&sort=new" `
  5 'name="exhibit_data"' $false
if (-not ($ok1 -and $ok2)) { exit 1 }
