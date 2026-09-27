@echo off
rem chien 運用エージェント ワンクリック導入(docs/317)v4
rem  ダブルクリックだけ。管理者権限は不要(Python はユーザー領域に導入・タスクは現在ユーザーで登録)。
rem  画面は自動で閉じない(cmd /k)ので、止まった所が読める。ログは C:\chien\ops\setup.log。
if not "%~1"=="run" (
  start "chien setup" cmd /k ""%~f0" run"
  exit /b
)
chcp 65001 >nul
set "ROOT=C:\chien\ops"
set "RAW=https://raw.githubusercontent.com/iq87jun-star/chien-monitor/claude/prop-trading-new-methods-a8y3l1/ops/vps"
if not exist "%ROOT%" mkdir "%ROOT%"
echo [1/3] 最新のスクリプトを取得します
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; foreach($f in 'chien_ops_agent.py','terminals.example.json','setup.ps1','install_task.ps1'){ Invoke-WebRequest ('%RAW%/'+$f+'?t='+(Get-Date).Ticks) -OutFile (Join-Path '%ROOT%' $f) -UseBasicParsing; Write-Host ('  取得 '+$f) }"
if errorlevel 1 (
  echo ダウンロードに失敗しました。VPS からインターネットに出られるか確認してください。
  goto :end
)
echo [2/3] セットアップ(Python 導入・端末の自動検出・1 回実行・毎時タスク登録)。ログ: %ROOT%\setup.log
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%ROOT%\setup.ps1' 2>&1 | Tee-Object -FilePath '%ROOT%\setup.log'"
echo [3/3] 終了。Google Drive の chien_ops\<口座番号>\ に CSV があるか確認し、チャットで「エージェント稼働」と伝えてください。
:end
echo.
echo この画面は閉じずに、写真を撮って送ってください。
