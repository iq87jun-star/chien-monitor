@echo off
rem chien 運用エージェント ワンクリック導入(docs/317)。ダブルクリック → UAC「はい」だけで、
rem Git 導入 → リポジトリ取得 → Python 導入 → 端末の自動検出 → 1 回実行 → 毎時タスク登録 まで進む。
chcp 65001 >nul
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 管理者権限で再起動します...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "ROOT=C:\chien\chien-monitor"
set "BRANCH=claude/prop-trading-new-methods-a8y3l1"
set "PATH=%PATH%;C:\Program Files\Git\cmd;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
where git >nul 2>&1 || (
  echo [1/4] Git を導入します
  winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
  set "PATH=%PATH%;C:\Program Files\Git\cmd"
)
if not exist "%ROOT%\.git" (
  echo [2/4] リポジトリを取得します(GitHub のログイン画面が出たらブラウザで承認)
  git clone https://github.com/iq87jun-star/chien-monitor.git "%ROOT%" || (echo clone に失敗しました & pause & exit /b 1)
)
cd /d "%ROOT%"
git fetch origin %BRANCH% && git checkout %BRANCH% && git pull origin %BRANCH%
echo [3/4] セットアップ(Python・端末検出・1 回実行・タスク登録)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\ops\vps\setup.ps1"
echo [4/4] 完了。Drive の chien_ops\<口座>\ に CSV があるか確認し、チャットで「エージェント稼働」と伝えてください。
pause
