@echo off
rem chien 運用エージェント ワンクリック導入(docs/317)v3
rem  ダブルクリック → UAC「はい」だけ。Git / GitHub Desktop / winget は不要。
rem  必要な 4 ファイルを GitHub(公開リポジトリ)から直接ダウンロードし、C:\chien\ops に置いて setup.ps1 を実行する。
rem  2 回目以降の実行では最新版に自動更新してから実行する(terminals.json は上書きしない)。
chcp 65001 >nul
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 管理者権限で再起動します...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "ROOT=C:\chien\ops"
set "RAW=https://raw.githubusercontent.com/iq87jun-star/chien-monitor/claude/prop-trading-new-methods-a8y3l1/ops/vps"
if not exist "%ROOT%" mkdir "%ROOT%"
echo [1/3] 最新のスクリプトを取得します
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; foreach($f in 'chien_ops_agent.py','terminals.example.json','setup.ps1','install_task.ps1'){ Invoke-WebRequest ('%RAW%/'+$f+'?t='+(Get-Date).Ticks) -OutFile (Join-Path '%ROOT%' $f) -UseBasicParsing; Write-Host ('  取得 '+$f) }" || (echo ダウンロードに失敗しました。VPS からインターネットに出られるか確認してください。 & pause & exit /b 1)
echo [2/3] セットアップ(Python 導入・端末の自動検出・1 回実行・毎時タスク登録)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\setup.ps1"
echo [3/3] 完了。Google Drive の chien_ops\<口座番号>\ に CSV があるか確認し、チャットで「エージェント稼働」と伝えてください。
pause
