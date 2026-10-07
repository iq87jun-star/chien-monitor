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
function Send($bodyFile, $path = "/ingest") {
  $resFile = Join-Path $env:TEMP "gamewatch_res.json"
  $errFile = Join-Path $env:TEMP "gamewatch_err.txt"
  Remove-Item $resFile, $errFile -ErrorAction SilentlyContinue
  $code = curl.exe -sS --connect-timeout 20 --max-time 180 --retry 3 --retry-delay 20 --retry-all-errors `
    -o $resFile -w "%{http_code}" -X POST "$worker$path" `
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

# Read a JSON file from GitHub (?v= avoids GitHub's cache). Download to a file and read it as UTF-8:
# curl's console output is decoded with the Japanese code page in PowerShell 5.1, which garbles Japanese text
# and can break the JSON.
function GetJson($file) {
  $f = Join-Path $env:TEMP "gamewatch_cfg.json"
  Remove-Item $f -ErrorAction SilentlyContinue
  curl.exe -sSf --connect-timeout 20 --retry 2 --retry-all-errors -o $f "$raw/$($file)?v=$(Get-Date -Format yyyyMMddHHmmss)"
  if ($LASTEXITCODE -ne 0) { throw "could not read $file" }
  return ([System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8) | ConvertFrom-Json)
}

# The listing URL (price range) and page count come from the site's config on GitHub, so changing them needs
# no reinstall. ?v= avoids GitHub's cache. Falls back to the built-in values if GitHub can't be reached.
function SiteConfig($file, $url, $pages) {
  try {
    $cfg = GetJson $file
    if ($cfg.url) { $url = [string]$cfg.url }
    if ($cfg.pages) { $pages = [int]$cfg.pages }
  } catch {}
  return @($url, $pages)
}

# Fetch up to $maxPages pages. $marker must appear in a real listing page. With $stopAtLast, stop at the page
# without a "next" link (GameClub filters the price range itself, so the range fits in a few pages).
# $script:pagesComplete tells whether every page was read (with $stopAtLast: the last page had no "next" link).
function FetchPages($site, $base, $maxPages, $marker, $stopAtLast) {
  $pages = @()
  $script:pagesComplete = $false
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
    if ($stopAtLast -and $html -notmatch 'class="pager-next"') { $script:pagesComplete = $true; break }  # last page
    Start-Sleep -Seconds 3
  }
  return ,$pages
}

# $cfgFile: the site's config on GitHub, or "" to use $defaultUrl / $defaultPages as given (config.targets.json)
function RunSite($site, $cfgFile, $defaultUrl, $defaultPages, $marker, $stopAtLast) {
  try {
    $cfg = if ($cfgFile) { SiteConfig $cfgFile $defaultUrl $defaultPages } else { @($defaultUrl, $defaultPages) }
    $pages = FetchPages $site $cfg[0] $cfg[1] $marker $stopAtLast
    # complete=false: more pages than $maxPages, so the Worker must not assume it saw the whole price range
    $r = Send (WriteJson @{ site = $site; pages = $pages; complete = [bool]$script:pagesComplete } "$($site)_body.json")
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

# Sold accounts (for the account price tool): GameTrade keeps finished trades in its listing as SOLD with the price.
# Send the listing pages of each game (all items, newest first, price range from config.sold.json) to /sold/pages,
# then fill in the full description and images of new ones: ask /sold/missing, fetch each listing page and send
# its HTML to /sold/detail-html. The Worker does the parsing. A failure here does not fail the task.
function RunSold() {
  try {
    $cfg = GetJson "config.sold.json"
    $added = 0
    foreach ($g in $cfg.games) {
      $base = "https://gametrade.jp/$($g.game)/exhibits?filter=all&sort=new&low_price=$($cfg.low)&high_price=$($cfg.high)"
      $pages = FetchPages "sold_$($g.game)" $base ([int]$cfg.pages) 'name="exhibit_data"' $false
      # 5 pages per request keeps each request small
      for ($i = 0; $i -lt $pages.Count; $i += 5) {
        $chunk = @($pages[$i..([Math]::Min($i + 4, $pages.Count - 1))])
        $r = Send (WriteJson @{ game = $g.game; pages = $chunk } "sold_body.json") "/sold/pages"
        if ($r[0] -ne "200") { throw "sold/pages $($g.game) HTTP $($r[0]) ($($r[2])): $($r[1])" }
        $added += [int](($r[1] | ConvertFrom-Json).added)
      }
    }
    # Listings still missing the full description
    $missFile = Join-Path $env:TEMP "sold_missing.json"
    $code = curl.exe -sS --connect-timeout 20 --max-time 60 --retry 2 --retry-all-errors -o $missFile -w "%{http_code}" `
      -H "authorization: Bearer $token" "$worker/sold/missing?limit=$([int]$cfg.details)"
    if ($code -ne "200") { throw "sold/missing HTTP $code" }
    $missing = ([System.IO.File]::ReadAllText($missFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json).items
    $filled = 0
    foreach ($m in $missing) {
      Start-Sleep -Seconds 2
      $f = Join-Path $env:TEMP "sold_detail.html"
      Remove-Item $f -ErrorAction SilentlyContinue
      $c = curl.exe -s --connect-timeout 20 --max-time 60 --retry 2 --retry-delay 10 --retry-all-errors -A $ua -H "accept-language: ja" -o $f -w "%{http_code}" $m.url
      if ($c -ne "200") { continue }  # deleted listing etc.; tried again next time
      $html = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
      $r = Send (WriteJson @{ id = [string]$m.id; html = $html } "sold_detail.json") "/sold/detail-html"
      if ($r[0] -eq "200") { $filled++ }
    }
    Log "sold ok added=$added details=$filled/$($missing.Count)"
  } catch {
    $msg = $_.Exception.Message
    Log "sold error $msg"
    try { [void](Send (WriteJson @{ site = "gametrade"; error = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') sold: $msg" } "sold_error.json")) } catch {}
  }
}

$token = (Get-Content (Join-Path $dir "token.txt") -Raw).Trim()
$ok1 = RunSite "gameclub" "config.gameclub.json" `
  "https://gameclub.jp/genshin-impact?search%5Btype%5D%5B1%5D=1&search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000" `
  10 'class="item-row' $true
$ok2 = RunSite "gametrade" "config.json" `
  "https://gametrade.jp/genshin-impact/exhibits?5star-character=all&exclude_keyword=&filter=purchasable&genseki=all&high_price=200000&identity_verification=checked&keyword=&low_price=70000&rank=all&sort=new" `
  5 'name="exhibit_data"' $false
# Other games (Zenless Zone Zero, Wuthering Waves, ...): config.targets.json on GitHub lists them,
# so adding a game needs no change on this PC. "site" is the kind of page: gametrade or gameclub.
$ok3 = $true
try {
  foreach ($t in (GetJson "config.targets.json")) {
    if ($t.site -eq "gameclub") { $marker = 'class="item-row'; $last = $true } else { $marker = 'name="exhibit_data"'; $last = $false }
    if (-not (RunSite ([string]$t.id) "" ([string]$t.url) ([int]$t.pages) $marker $last)) { $ok3 = $false }
  }
} catch {
  Log "targets error $($_.Exception.Message)"
  $ok3 = $false
}
RunSold
if (-not ($ok1 -and $ok2 -and $ok3)) { exit 1 }
