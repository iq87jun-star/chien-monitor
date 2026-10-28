# theoption 実口座用 API キーの入力だけを行う(画面に出さない・ユーザー環境変数 THEOPTION_API_KEY_REAL に保存)→ 実口座の health/残高を読むだけの接続確認(発注しない)。
# 実口座での発注は、これに加えて to_config.json の "live_real": true が必要(二重オプトイン)。この script は to_config.json を変更しない。
$here = Split-Path -Parent $MyInvocation.MyCommand.Path; Set-Location $here
Write-Host "theoption → 自動売買用API →「リアル」タブ →「APIキーをリクエスト」で出たキーを貼り付けて Enter(画面には表示されない)"
$sec = Read-Host "実口座APIキー" -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
if (-not $key) { Write-Host "キーが空。中止" -ForegroundColor Red; exit 1 }
[Environment]::SetEnvironmentVariable("THEOPTION_API_KEY_REAL", $key, "User"); $env:THEOPTION_API_KEY_REAL = $key
Write-Host "保存しました。実口座の接続確認(health・残高のみ、発注しない)..."
$py = @'
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ".")
import to_live as L
key = os.environ.get("THEOPTION_API_KEY_REAL", "").strip()
iss = L.jwt_iss(key); print("JWT iss:", iss)
if not L.key_matches_account("real", key): print("このキーは実口座用ではありません(お試し用キーの可能性)。THEOPTION_API_KEY_REAL を入れ直してください"); sys.exit(2)
base, _ = L.HOSTS["real"]
st, h = L.rest(base, "/trading/health", key); print("health:", st, h)
st, b = L.rest(base, "/wallet/balance", key); print("balance:", st, b)
import json; cfg = {}
try: cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(L.__file__)), "to_config.json"), encoding="utf-8"))
except Exception: pass
print("to_config.json live_real =", cfg.get("live_real"), "→ 実口座で発注するには true が必要(11/3 の突合で切替判定)")
'@
$tmp = Join-Path $here "_check_real.py"; Set-Content -Path $tmp -Value $py -Encoding UTF8
& python $tmp; Remove-Item $tmp -ErrorAction SilentlyContinue
