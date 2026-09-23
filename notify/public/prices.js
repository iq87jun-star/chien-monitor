// 相場データ(拡張と同じ v1 形式の JSON)を「通知対象のカード」の一覧にする。
// 登録ページ(ブラウザ)と値下がりチェック(GitHub Actions の node)の両方から読み込む。
// データ形式は toreca/pipeline/export-ext.mjs・export-onepiece.mjs と duel/pipeline/export-ext.mjs と対応。
// カード行: [setId, localId, 名前(文字列、または別名の配列で先頭が表示名), 価格, avg7, avg30, 補足, 版]

export const FORMAT_VERSION = 1;

export const SOURCES = [
  {
    game: "pokeca",
    name: "ポケカ",
    url: "https://pokeca-kaigai.com/api/cards.json",
    siteUrl: "https://pokeca-kaigai.com/",
    disclaimer: "日本語版の欧州相場(Cardmarket)を円換算した参考値です",
  },
  {
    game: "yugioh",
    name: "遊戯王",
    url: "https://pocketduel.tokyo/api/cards.json",
    siteUrl: "https://pocketduel.tokyo/",
    disclaimer: "英語版で最も安い版の欧州相場を円換算した参考値です",
  },
  {
    game: "onepiece",
    name: "ワンピース",
    url: "https://pokeca-kaigai.com/api/onepiece.json",
    siteUrl: null,
    disclaimer: "英語版カードの米国相場(TCGplayer)を円換算した参考値です",
  },
];

// 全角英数→半角、ひらがな→カタカナ、小文字化、空白と記号の除去(拡張の matcher.js と同じ規則)
export function normalize(s) {
  return String(s ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ぁ-ゖ]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) + 0x60))
    .replace(/[\s・･\-‐－―~〜「」『』【】\[\]()（）<>＜＞!！?？、。,.:：/／★☆◆◇#＃"]/g, "");
}

// 遊戯王の英語名は '"7"' のように引用符つきのことがある
const unquote = (s) => String(s ?? "").replace(/^"(.*)"$/, "$1");

// 1つの価格データ → [{ key, game, label, sub, jpy, search }]
// key は通知の登録に使う識別子で、データが更新されても変わらないものにする:
//   ポケカ   pokeca:<セット>-<番号>
//   遊戯王   yugioh:<英語名>(セット・番号を持たないデータのため)
//   ワンピース onepiece:<カード番号>:<版>(同じ番号・版の再録は最安値にまとめる)
export function buildCards(game, data) {
  if (!data || data.v !== FORMAT_VERSION || !data.available || !Array.isArray(data.cards))
    return [];
  const rate = data.rateJpy ?? data.eurJpy;
  if (!rate) return [];
  const setNames = new Map((data.sets ?? []).map((s) => [s.id, s.name]));
  const variantLabels = data.variantLabels ?? {};
  const byKey = new Map();
  for (const [setId, localId, nameOrNames, price, , , note, variant] of data.cards) {
    if (typeof price !== "number" || !(price > 0)) continue;
    const names = Array.isArray(nameOrNames) ? nameOrNames : [nameOrNames];
    const jpy = Math.round(price * rate);
    let card;
    if (game === "pokeca") {
      const setName = setNames.get(setId) ?? setId;
      card = {
        key: `pokeca:${setId}-${localId}`,
        label: names[0],
        sub: `${setName} ${localId}`,
      };
    } else if (game === "onepiece") {
      const v = variant ?? "normal";
      card = {
        key: `onepiece:${localId}:${v}`,
        label: `${localId} ${names[0]}`,
        sub: variantLabels[v] ?? v,
      };
    } else {
      const en = unquote(note) || names[0];
      card = { key: `${game}:${en}`, label: names[0].replace(/^『(.*)』$/, "$1"), sub: en };
    }
    const prev = byKey.get(card.key);
    if (prev && prev.jpy <= jpy) continue;
    byKey.set(card.key, {
      ...card,
      game,
      jpy,
      search: normalize([card.label, card.sub, ...names].join(" ")),
    });
  }
  return [...byKey.values()];
}

// 全ゲームの相場を取得する。取得に失敗したゲームは errors に入れ、他のゲームは続ける
export async function loadPrices(fetchImpl = fetch) {
  const cards = new Map();
  const sources = {};
  const errors = {};
  await Promise.all(
    SOURCES.map(async (src) => {
      try {
        const res = await fetchImpl(src.url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const list = buildCards(src.game, data);
        if (list.length === 0) throw new Error("no cards");
        for (const c of list) cards.set(c.key, c);
        sources[src.game] = { ...src, fetchedAt: data.fetchedAt ?? null, count: list.length };
      } catch (err) {
        errors[src.game] = err.message;
      }
    }),
  );
  return { cards, sources, errors };
}

// 検索: 空白で区切った語をすべて含むカード。完全一致・前方一致を先に、あとは価格の高い順。
// game を指定するとそのゲームだけ(ワンピースは英語名しかないので、他ゲームのカタカナ名に紛れないように)
export function searchCards(cards, query, { game = null, limit = 30 } = {}) {
  const terms = String(query ?? "")
    .split(/[\s　]+/)
    .map(normalize)
    .filter(Boolean);
  if (terms.length === 0) return [];
  const first = terms[0];
  const rank = (c) => {
    const name = normalize(c.label);
    return name === first ? 0 : name.startsWith(first) ? 1 : 2;
  };
  return [...cards.values()]
    .filter((c) => (!game || c.game === game) && terms.every((t) => c.search.includes(t)))
    .sort((a, b) => rank(a) - rank(b) || b.jpy - a.jpy)
    .slice(0, limit);
}

export const gameOf = (key) => SOURCES.find((s) => key.startsWith(`${s.game}:`)) ?? null;

export const yen = (n) => `${Math.round(n).toLocaleString("ja-JP")}円`;
