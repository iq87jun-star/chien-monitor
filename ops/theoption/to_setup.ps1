# theoption プローブの VPS 初回セットアップ(to_setup.bat から呼ばれる)。管理者権限は不要。取引はしない。
# やること: Python 確認 → pip websockets → お試し用 API キーの入力(画面に出さない・ユーザー環境変数に保存)→ Drive の chien_ops\theoption を記録先に
#          → 接続確認(60 秒)→ タスク登録(月曜 05:25〜09:30 の記録 / 平日 12:00 の接続確認)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path; Set-Location $here
function Step($s){ Write-Host "`n=== $s ===" -ForegroundColor Cyan }

Step "1. Python"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  Write-Host "Python 3.11 を公式サイトから導入"
  $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"; $f = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
  Invoke-WebRequest $url -OutFile $f
  Start-Process -Wait -FilePath $f -ArgumentList "/quiet","InstallAllUsers=0","PrependPath=1","Include_test=0"
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
$env:PYTHONUTF8 = "1"; & python --version
& python -m pip install --quiet --upgrade websockets
Write-Host "pip: websockets 導入済み"

Step "2. お試し用 API キー"
$cur = [Environment]::GetEnvironmentVariable("THEOPTION_API_KEY", "User")
if ($cur) { Write-Host "登録済み(末尾 ...$($cur.Substring([Math]::Max(0,$cur.Length-4))))。変えるときは to_setup.bat を -NewKey 付きで" }
if (-not $cur -or $args -contains "-NewKey") {
  Write-Host "theoption → 自動売買用API →「お試し」タブ →「APIキーをリクエスト」で出たキーを貼り付けて Enter(画面には表示されない)"
  $sec = Read-Host "APIキー" -AsSecureString
  $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
  if (-not $key) { Write-Host "キーが空。中止" -ForegroundColor Red; exit 1 }
  [Environment]::SetEnvironmentVariable("THEOPTION_API_KEY", $key, "User"); $cur = $key
  Write-Host "ユーザー環境変数 THEOPTION_API_KEY に保存(ファイルには書かない)"
}
$env:THEOPTION_API_KEY = $cur

Step "3. 記録先(Google Drive)"
$out = ""
foreach ($d in (Get-PSDrive -PSProvider FileSystem)) { foreach ($n in @("マイドライブ","My Drive")) { $p = Join-Path $d.Root $n; if ((Test-Path $p) -and -not $out) { $out = Join-Path $p "chien_ops\theoption" } } }
if (-not $out) { $out = Join-Path $here "out"; Write-Host "Google Drive が見つからない → $out に記録(チャットからは読めない)" -ForegroundColor Yellow } else { Write-Host "記録先: $out" }
New-Item -ItemType Directory -Force -Path $out | Out-Null
@{ out = $out } | ConvertTo-Json | Set-Content (Join-Path $here "to_config.json") -Encoding UTF8

Step "4. 接続確認(60 秒・取引しない)"
& (Join-Path $here "to_run.ps1") -Mode check
Get-Content (Join-Path $here "run.log") -Tail 40

Step "5. タスク登録"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 5) -MultipleInstances IgnoreNew
$ps = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $here 'to_run.ps1')`""
foreach ($t in @(@("monday", "Monday", "05:25"), @("check", @("Tuesday","Wednesday","Thursday","Friday"), "12:00"))) {
  $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "$ps -Mode $($t[0])" -WorkingDirectory $here
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $t[1] -At $t[2]
  Register-ScheduledTask -TaskName "chien_theoption_$($t[0])" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "登録: chien_theoption_$($t[0])  $($t[1] -join ',') $($t[2]) JST"
}
Write-Host "`n完了。記録と要約は $out に出る(Drive 経由でチャットから読める)。チャットに「theoption 設定完了」と一言。" -ForegroundColor Green
