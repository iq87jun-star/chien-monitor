#!/bin/bash
# docs/254: 2 時間毎 Routine から呼ぶ。実測 ≈48 ファイル/時のため範囲を縮小: ①新 19 銘柄 bid 2018-01〜(1,976)②既存 19 銘柄 ask 2024-01〜(608)。部分保存・manifest.json で再開。
cd /home/user/chien-monitor
NEW="EURCHF=EURCHF,GBPCHF=GBPCHF,AUDNZD=AUDNZD,AUDCAD=AUDCAD,BRENT=BRENTCMDUSD,WTI=LIGHTCMDUSD,UK100=GBRIDXGBP,JP225=JPNIDXJPY,EUSTX50=EUSIDXEUR,US30=USA30IDXUSD,AUS200=AUSIDXAUD,HK50=HKGIDXHKD,BUND=BUNDTREUR,USTBOND=USTBONDTRUSD,DXY=DOLLARIDXUSD,XAGUSD=XAGUSD,NZDCAD=NZDCAD,CADCHF=CADCHF,USDCAD=USDCAD"   # docs/255: 指数・商品・債券を先に(FX クロスは結果が見えているため後回し)
OLD="EURGBP=EURGBP,USDCHF=USDCHF,NZDUSD=NZDUSD,AUDUSD=AUDUSD,CHFJPY=CHFJPY,GBPJPY=GBPJPY,EURJPY=EURJPY,AUDJPY=AUDJPY,USDJPY=USDJPY,CADJPY=CADJPY,NZDJPY=NZDJPY,EURUSD=EURUSD,GBPUSD=GBPUSD,EURAUD=EURAUD,GBPAUD=GBPAUD,XAUUSD=XAUUSD,GER40=DEUIDXEUR,NAS100=USATECHIDXUSD,US500=USA500IDXUSD"
T0=$(date +%s); B=${1:-48}
left() { echo $(( B - ($(date +%s) - T0) / 60 )); }
python3 research/tools/dukascopy_fetch.py bid "$NEW" 2018-01 2026-08 "$(left)"
[ "$(left)" -gt 2 ] && python3 research/tools/dukascopy_fetch.py ask "$OLD" 2024-01 2026-08 "$(left)"
# ③新銘柄 ask は実測ペース(≈48 ファイル/時)では間に合わないため保留(docs/254)
python3 - <<'PY'
import json,os
m=json.load(open("/home/user/chien-monitor/research/data_dukascopy/manifest.json")) if os.path.exists("/home/user/chien-monitor/research/data_dukascopy/manifest.json") else {}
done=[k for k,v in m.items() if v.get("complete")]; part=[k for k,v in m.items() if not v.get("complete")]
print(f"[SUMMARY] complete={len(done)}/38 partial={len(part)} {part[:3]}")
PY
