#!/bin/bash
# docs/254: 毎時 Routine から呼ぶ。時間予算 48 分で ①新銘柄 bid ②既存 ask ③新銘柄 ask を順に進め、部分保存して終了。manifest.json で再開。
cd /home/user/chien-monitor
NEW="EURCHF=EURCHF,GBPCHF=GBPCHF,AUDNZD=AUDNZD,AUDCAD=AUDCAD,NZDCAD=NZDCAD,CADCHF=CADCHF,USDCAD=USDCAD,XAGUSD=XAGUSD,BRENT=BRENTCMDUSD,WTI=LIGHTCMDUSD,UK100=GBRIDXGBP,JP225=JPNIDXJPY,EUSTX50=EUSIDXEUR,US30=USA30IDXUSD,AUS200=AUSIDXAUD,HK50=HKGIDXHKD,BUND=BUNDTREUR,USTBOND=USTBONDTRUSD,DXY=DOLLARIDXUSD"
OLD="EURGBP=EURGBP,USDCHF=USDCHF,NZDUSD=NZDUSD,AUDUSD=AUDUSD,CHFJPY=CHFJPY,GBPJPY=GBPJPY,EURJPY=EURJPY,AUDJPY=AUDJPY,USDJPY=USDJPY,CADJPY=CADJPY,NZDJPY=NZDJPY,EURUSD=EURUSD,GBPUSD=GBPUSD,EURAUD=EURAUD,GBPAUD=GBPAUD,XAUUSD=XAUUSD,GER40=DEUIDXEUR,NAS100=USATECHIDXUSD,US500=USA500IDXUSD"
T0=$(date +%s); B=${1:-48}
left() { echo $(( B - ($(date +%s) - T0) / 60 )); }
python3 research/tools/dukascopy_fetch.py bid "$NEW" 2016-01 2026-08 "$(left)"
[ "$(left)" -gt 2 ] && python3 research/tools/dukascopy_fetch.py ask "$OLD" 2016-01 2026-08 "$(left)"
[ "$(left)" -gt 2 ] && python3 research/tools/dukascopy_fetch.py ask "$NEW" 2016-01 2026-08 "$(left)"
python3 - <<'PY'
import json,os
m=json.load(open("/home/user/chien-monitor/research/data_dukascopy/manifest.json")) if os.path.exists("/home/user/chien-monitor/research/data_dukascopy/manifest.json") else {}
done=[k for k,v in m.items() if v.get("complete")]; part=[k for k,v in m.items() if not v.get("complete")]
print(f"[SUMMARY] complete={len(done)}/57 partial={len(part)} {part[:3]}")
PY
