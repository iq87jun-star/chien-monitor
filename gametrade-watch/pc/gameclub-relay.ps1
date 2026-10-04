# ゲームクラブ(gameclub.jp)の一覧ページを取得して Cloudflare Worker(src/worker.js)に送る。
# ゲームクラブはクラウドのサーバーからのアクセスにボット対策の確認画面を返すため、自宅の PC から毎晩実行する。
# 判定・Discord 通知・状態の保存は Worker が行う。登録は pc/install-gameclub.ps1。
#
#   powershell -ExecutionPolicy Bypass -File gameclub-relay.ps1
#
# 合言葉は同じフォルダの token.txt(リポジトリには入れない)。ログは同じフォルダの relay.log。

$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
$log = Join-Path $dir "relay.log"
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Tee-Object -FilePath $log -Append }

try {
  $token = (Get-Content (Join-Path $dir "token.txt") -Raw).Trim()
  $base = "https://gameclub.jp/genshin-impact?search%5Btype%5D%5B1%5D=1&search%5BpriceMin%5D=75000&search%5BpriceMax%5D=150000"
  $ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
  $pages = @()
  for ($p = 1; $p -le 5; $p++) {
    $f = Join-Path $env:TEMP "gameclub_p$p.html"
    $code = curl.exe -s -A $ua -o $f -w "%{http_code}" "$base&page=$p"
    if ($code -ne "200") { throw "page $p: HTTP $code" }
    $html = Get-Content $f -Raw -Encoding UTF8
    if ($html -match "Just a moment") { throw "page $p: ボット対策の確認画面が返った" }
    $pages += $html
    if ($html -notmatch 'class="pager-next"') { break }  # 最後のページ
    Start-Sleep -Seconds 3
  }
  $body = @{ site = "gameclub"; pages = $pages } | ConvertTo-Json -Compress
  $res = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "https://gametrade-watch.iq87jun.workers.dev/ingest" `
    -Headers @{ authorization = "Bearer $token" } -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
  Log "ok pages=$($pages.Count) $($res.Content)"
} catch {
  $detail = $_.Exception.Message
  if ($_.Exception.Response) {
    try { $detail += " " + (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch {}
  }
  Log "error $detail"
  exit 1
}
