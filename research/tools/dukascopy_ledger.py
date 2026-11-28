"""docs/254 用: research/data_dukascopy/ の台帳(銘柄・bid/ask・期間・行数・欠損月)を Markdown 表で出力する。
使い方: cd research && python3 tools/dukascopy_ledger.py > /tmp/ledger.md
"""
import gzip, json, os, glob, io
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_dukascopy')
man = json.load(open(os.path.join(ROOT, 'manifest.json')))
CODES = {'BRENT':'BRENTCMDUSD','WTI':'LIGHTCMDUSD','UK100':'GBRIDXGBP','JP225':'JPNIDXJPY','EUSTX50':'EUSIDXEUR','US30':'USA30IDXUSD','AUS200':'AUSIDXAUD','HK50':'HKGIDXHKD','BUND':'BUNDTREUR','USTBOND':'USTBONDTRUSD','DXY':'DOLLARIDXUSD','GER40':'DEUIDXEUR','NAS100':'USATECHIDXUSD','US500':'USA500IDXUSD'}
def span(path):
    first = last = None; n = 0
    with gzip.open(path, 'rt') as f:
        f.readline()
        for line in f:
            t = line[:10]
            if first is None: first = t
            last = t; n += 1
    return first, last, n
rows = []
for f in sorted(glob.glob(os.path.join(ROOT, '*_hour*.csv.gz'))):
    base = os.path.basename(f)
    sym = base.split('_hour')[0]; side = 'ask' if base.endswith('_ask.csv.gz') else 'bid'
    first, last, n = span(f)
    m = man.get(f'{sym}|{side}', {})
    rows.append((sym, side, CODES.get(sym, sym), first, last, n, m.get('done_months', ''), 'yes' if m.get('complete') else ('manifest外' if not m else 'no'), ','.join(m.get('missing404', [])) or '-'))
print('| 銘柄 | 側 | Dukascopy コード | 開始 | 終了 | 行数 | 月数 | 完了 | 404 月 |')
print('|---|---|---|---|---|--:|--:|---|---|')
for r in rows: print('| ' + ' | '.join(str(x) for x in r) + ' |')
print()
print(f'ファイル数 {len(rows)}・manifest complete {sum(1 for v in man.values() if v.get("complete"))}/{len(man)}')
