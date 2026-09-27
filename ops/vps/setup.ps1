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

Step "3-4. MT5 端末の自動検出 → terminals.json 生成(各端末に接続して口座番号を読む)"
$cfg = Join-Path $here "terminals.json"
& python (Join-Path $here "chien_ops_agent.py") --discover --config $cfg --out $DriveRoot
if ($LASTEXITCODE -ne 0) {
  Write-Host "未接続の端末があります(未ログインか、標準外の場所)。terminals.json の enabled=false の行に login/password を記入して保存してください。" -ForegroundColor Yellow
  notepad $cfg
  Read-Host "保存したら Enter"
} else { Write-Host "全端末を自動検出しました(パスワード記入は不要)" -ForegroundColor Green }

Step "5. 手動 1 回実行(端末ごとに ok が出るか)"
& python (Join-Path $here "chien_ops_agent.py") --config $cfg
Write-Host "→ 失敗した端末があれば terminals.json を直して再実行: python chien_ops_agent.py --config terminals.json"

Step "6. 毎時タスク登録"
& powershell -ExecutionPolicy Bypass -File (Join-Path $here "install_task.ps1")
Write-Host "`n完了。Drive の chien_ops\<口座>\ に CSV が出ていれば、チャットで「エージェント稼働」と一言。" -ForegroundColor Green
