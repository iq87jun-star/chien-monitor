# theoption お試し用 API キーの入力だけを行う(画面に出さない・ユーザー環境変数に保存)→ 60 秒の接続確認。
$here = Split-Path -Parent $MyInvocation.MyCommand.Path; Set-Location $here
Write-Host "theoption → 自動売買用API →「お試し」タブ →「APIキーをリクエスト」で出たキーを貼り付けて Enter(画面には表示されない)"
$sec = Read-Host "APIキー" -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
if (-not $key) { Write-Host "キーが空。中止" -ForegroundColor Red; exit 1 }
[Environment]::SetEnvironmentVariable("THEOPTION_API_KEY", $key, "User"); $env:THEOPTION_API_KEY = $key
Write-Host "保存しました。接続確認(60 秒・取引しない)..."
& (Join-Path $here "to_run.ps1") -Mode check; Get-Content (Join-Path $here "run.log") -Tail 30
