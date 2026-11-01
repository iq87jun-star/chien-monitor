// 日本証券金融(日証金)の公開CSVの取得と読み取り。
//   品貸料率一覧 https://www.taisyaku.jp/data/shina.csv(最高料率・当日品貸料率・制限)
//   貸借取引残高 https://www.taisyaku.jp/data/zandaka.csv(株価の目安に使う)
// どちらも Shift_JIS。毎朝 10:30 ごろ(JST)に前営業日の申込日分へ更新される。

export const SHINA_URL = 'https://www.taisyaku.jp/data/shina.csv';
export const ZANDAKA_URL = 'https://www.taisyaku.jp/data/zandaka.csv';

export function decodeSjis(buf) {
  return new TextDecoder('shift_jis').decode(buf);
}

// 引用符つきにも対応した素朴な CSV 分割
export function parseCsv(text) {
  const rows = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const out = [];
    let cur = '';
    let q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) {
        if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c;
      } else if (c === '"') q = true;
      else if (c === ',') { out.push(cur); cur = ''; } else cur += c;
    }
    out.push(cur);
    rows.push(out);
  }
  return rows;
}

const ymd = (s) => (/^\d{8}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : s.replaceAll('/', '-'));
const num = (s) => {
  const v = Number(String(s ?? '').replaceAll(',', ''));
  return s === '' || s == null || Number.isNaN(v) ? null : v;
};

// 品貸料率一覧 → 必要な列だけのオブジェクト
// 当日品貸料率は「1株あたり・品貸日数分」の金額(***** は品貸なし=0 円)
export function parseShina(text) {
  const rows = parseCsv(text);
  const h = rows.findIndex((r) => r[0] === '貸借申込日');
  if (h < 0) throw new Error('品貸料率一覧の見出し行が見つからない(形式が変わった可能性)');
  return rows.slice(h + 1).filter((r) => r.length >= 15 && /^\d{8}$/.test(r[0])).map((r) => ({
    date: ymd(r[0]),
    settle: ymd(r[1]),
    code: r[2],
    name: r[3],
    event: r[5],
    eventDate: ymd(r[6]),
    price: num(r[7]),
    excess: num(r[8]) ?? 0,
    maxRate: num(r[9]),
    rate: r[10].includes('*') ? 0 : num(r[10]),
    days: num(r[11]),
    restrict: r[14] || '',
  }));
}

// 貸借取引残高 → コードごとの株価の目安(残高金額 / 残高株数)
export function parseZandakaPrices(text) {
  const rows = parseCsv(text);
  const h = rows.findIndex((r) => r[0] === '申込日');
  if (h < 0) throw new Error('貸借取引残高の見出し行が見つからない(形式が変わった可能性)');
  const prices = new Map();
  for (const r of rows.slice(h + 1)) {
    const code = r[2];
    const pairs = [[num(r[16]), num(r[9])], [num(r[19]), num(r[12])], [num(r[14]), num(r[7])]];
    for (const [amt, sh] of pairs) {
      if (amt && sh) { prices.set(code, Math.round((amt / sh) * 10) / 10); break; }
    }
  }
  return prices;
}

// 保存用: 1 行 1 銘柄の UTF-8 CSV
export const SLIM_HEADER = 'date,settle,code,name,event,eventDate,price,excess,maxRate,rate,days,restrict';
export function toSlimCsv(rows) {
  const esc = (v) => (v == null ? '' : /[",]/.test(String(v)) ? `"${String(v).replaceAll('"', '""')}"` : String(v));
  return [SLIM_HEADER, ...rows.map((r) => SLIM_HEADER.split(',').map((k) => esc(r[k])).join(','))].join('\n') + '\n';
}

export function fromSlimCsv(text) {
  const [head, ...rows] = parseCsv(text);
  return rows.map((r) => {
    const o = Object.fromEntries(head.map((k, i) => [k, r[i]]));
    for (const k of ['price', 'excess', 'maxRate', 'rate', 'days']) o[k] = num(o[k]);
    return o;
  });
}

// 最高料率がまだ出ていない銘柄の推定: 貸借値段の 0.2% を 0.2 円単位に切り上げ(下限 1 円)。
// 2026-10 の実データで、引き上げのない銘柄はこの式に一致する。日証金は状況により
// この 2 倍・4 倍などへ引き上げるので、判定には maxRateStress を掛けて使う。
export function estimateMaxRate(price) {
  if (!price) return null;
  return Math.max(1, Math.round(Math.ceil((price * 0.002) / 0.2 - 1e-9) * 2) / 10);
}
