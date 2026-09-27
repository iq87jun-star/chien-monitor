@echo off
rem chien 運用エージェント ワンクリック導入(docs/317)。ダブルクリック → UAC「はい」だけで進む。
rem v2: winget が無い環境(Windows Server 等)でも動くよう、Git / Python は公式サイトから直接ダウンロードして導入。
rem     GitHub Desktop 同梱の git も自動で探す。
chcp 65001 >nul
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 管理者権限で再起動します...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "ROOT=C:\chien\chien-monitor"
set "BRANCH=claude/prop-trading-new-methods-a8y3l1"
rem このファイルがリポジトリ内(ops\vps)にあるなら、その clone をそのまま使う
if exist "%~dp0..\..\.git" (for %%I in ("%~dp0..\..") do set "ROOT=%%~fI")
set "PATH=%PATH%;C:\Program Files\Git\cmd;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;C:\Program Files\Python311;C:\Program Files\Python311\Scripts"
rem GitHub Desktop 同梱の git
for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do if exist "%%D\resources\app\git\cmd\git.exe" set "PATH=%PATH%;%%D\resources\app\git\cmd"
where git >nul 2>&1 || (
  echo [1/4] Git を導入します(公式サイトから直接ダウンロード)
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$r=Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'; $a=$r.assets | Where-Object { $_.name -match '^Git-.*-64-bit\.exe$' } | Select-Object -First 1; $f=Join-Path $env:TEMP $a.name; Invoke-WebRequest $a.browser_download_url -OutFile $f; Start-Process -Wait -FilePath $f -ArgumentList '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-'"
  set "PATH=%PATH%;C:\Program Files\Git\cmd"
)
where git >nul 2>&1 || (echo Git が導入できませんでした。GitHub Desktop で clone してから、このファイルを再実行してください。 & pause & exit /b 1)
if not exist "%ROOT%\.git" (
  echo [2/4] リポジトリを取得します(GitHub のログイン画面が出たらブラウザで承認)
  git clone https://github.com/iq87jun-star/chien-monitor.git "%ROOT%" || (echo clone に失敗しました。GitHub Desktop で File - Clone repository から C:\chien\chien-monitor に clone してください。 & pause & exit /b 1)
)
cd /d "%ROOT%"
git fetch origin %BRANCH% && git checkout %BRANCH% && git pull origin %BRANCH%
echo [3/4] セットアップ(Python・端末検出・1 回実行・タスク登録)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\ops\vps\setup.ps1"
echo [4/4] 完了。Drive の chien_ops\<口座>\ に CSV があるか確認し、チャットで「エージェント稼働」と伝えてください。
pause
