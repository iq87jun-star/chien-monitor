// 日証金の CSV を取って data/jsf/shina-<申込日>.csv と data/prices-latest.csv に保存する。
// 品貸料率一覧は当日分しか公開されないので、毎営業日ためていく(紙上フォワードの採点に使う)。
import { mkdir, writeFile } from 'node:fs/promises';
import { SHINA_URL, ZANDAKA_URL, decodeSjis, parseShina, parseZandakaPrices, toSlimCsv } from './src/jsf.js';

async function get(url) {
  for (let i = 0; i < 4; i++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': 'yutai-monitor (personal research)' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return decodeSjis(new Uint8Array(await res.arrayBuffer()));
    } catch (e) {
      if (i === 3) throw new Error(`${url} の取得に失敗: ${e.message}`);
      await new Promise((r) => setTimeout(r, 2000 * 2 ** i));
    }
  }
}

const dir = new URL('./data/', import.meta.url);
await mkdir(new URL('./jsf/', dir), { recursive: true });

const shina = parseShina(await get(SHINA_URL));
if (!shina.length) throw new Error('品貸料率一覧が空');
const date = shina[0].date;
await writeFile(new URL(`./jsf/shina-${date}.csv`, dir), toSlimCsv(shina));

const prices = parseZandakaPrices(await get(ZANDAKA_URL));
const lines = ['code,price', ...[...prices].sort(([a], [b]) => a.localeCompare(b)).map(([c, p]) => `${c},${p}`)];
await writeFile(new URL('./prices-latest.csv', dir), lines.join('\n') + '\n');

console.log(`品貸料率一覧 申込日 ${date}: ${shina.length} 銘柄 / 株価 ${prices.size} 銘柄`);
