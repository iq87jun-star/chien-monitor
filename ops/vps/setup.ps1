# chien 運用エージェントの VPS 初回セットアップ(docs/317 §2 を 1 コマンドに)— 管理者 PowerShell で:
#   powershell -ExecutionPolicy Bypass -File setup.ps1 [-DriveRoot "G:\マイドライブ\chien_ops"] [-SkipPython]
# やること: Python 3.11(winget)→ pip(MetaTrader5, pandas)→ terminals.json の雛形生成(無ければ)→ MT5 端末の自動検出を表示
#          → 手動 1 回実行 → 毎時タスク登録。terminals.json の path/login/password は最後に手で確認・記入する。
param([string]$DriveRoot = "", [switch]$SkipPython)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
function Step($s){ Write-Host "`n=== $s ===" -ForegroundColor Cyan }

Step "1. Python"
if (-not $SkipPython) {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py -or -not ((& python --version 2>&1) -match "3\.1[1-3]")) {
    Write-Host "Python 3.11 を winget で導入"; winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  }
}
& python --version
& python -m pip install --quiet --upgrade pip
& python -m pip install --quiet MetaTrader5 pandas
Write-Host "pip: MetaTrader5 / pandas 導入済み"

Step "2. Google Drive 同期先"
if ($DriveRoot -eq "") {
  $cands = @()
  foreach ($d in (Get-PSDrive -PSProvider FileSystem)) { foreach ($n in @("マイドライブ","My Drive")) { $p = Join-Path $d.Root $n; if (Test-Path $p) { $cands += $p } } }
  if ($cands.Count -gt 0) { $DriveRoot = Join-Path $cands[0] "chien_ops"; Write-Host "Drive を検出: $DriveRoot" } else { $DriveRoot = Join-Path $here "out"; Write-Host "Google Drive for desktop が見つからない → 一時的に $DriveRoot に出力(後で terminals.json の out_root を Drive のパスに変える)" -ForegroundColor Yellow }
}
New-Item -ItemType Directory -Force -Path $DriveRoot | Out-Null

Step "3. MT5 端末の自動検出"
$terms = Get-ChildItem "C:\Program Files","C:\Program Files (x86)","$env:LOCALAPPDATA\Programs" -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName "terminal64.exe") }
foreach ($t in $terms) { Write-Host ("  " + (Join-Path $t.FullName "terminal64.exe")) }
if ($terms.Count -eq 0) { Write-Host "  terminal64.exe が見つからない(標準外の場所なら terminals.json に手で記入)" -ForegroundColor Yellow }

Step "4. terminals.json"
$cfg = Join-Path $here "terminals.json"
if (-not (Test-Path $cfg)) {
  $j = Get-Content (Join-Path $here "terminals.example.json") -Raw -Encoding UTF8 | ConvertFrom-Json
  $j.out_root = $DriveRoot
  # 検出した端末を順に当てはめる(口座は example の並び。違えば手で直す)
  for ($i = 0; $i -lt $j.terminals.Count; $i++) { if ($i -lt $terms.Count) { $j.terminals[$i].path = (Join-Path $terms[$i].FullName "terminal64.exe") } }
  $j | ConvertTo-Json -Depth 5 | Set-Content $cfg -Encoding UTF8
  Write-Host "雛形を生成: $cfg  → 各端末の path / account / login / server(/ password)を確認・修正してから手順 5 へ" -ForegroundColor Yellow
  notepad $cfg
  Read-Host "terminals.json を保存したら Enter"
} else { Write-Host "既存の terminals.json を使用" }

Step "5. 手動 1 回実行(端末ごとに ok が出るか)"
& python (Join-Path $here "chien_ops_agent.py") --config $cfg
Write-Host "→ 失敗した端末があれば terminals.json を直して再実行: python chien_ops_agent.py --config terminals.json"

Step "6. 毎時タスク登録"
& powershell -ExecutionPolicy Bypass -File (Join-Path $here "install_task.ps1")
Write-Host "`n完了。Drive の chien_ops\<口座>\ に CSV が出ていれば、チャットで「エージェント稼働」と一言。" -ForegroundColor Green
