// 商品タイトルとカード価格データの突き合わせ(純粋関数のみ・DOM非依存)。
// content script(クラシックスクリプト)と node:test の両方から読み込むため、
// export は使わず globalThis.PokecaMatcher に公開する。
// データ形式は toreca/pipeline/export-ext.mjs(v1)と対応。
(() => {
  const FORMAT_VERSION = 1;
  // これより短いカード名は誤検出が多いので照合しない(「グリ」「タロ」等が「グリーン」に当たる)
  const MIN_NAME_LENGTH = 3;
  // 異なるカード名がこれを超えて含まれるタイトルは「まとめ売り」とみなし表示しない
  const MAX_DISTINCT_NAMES = 3;

  // 全角英数→半角、ひらがな→カタカナ、小文字化、空白と記号の除去
  function normalize(s) {
    return String(s ?? "")
      .normalize("NFKC")
      .toLowerCase()
      .replace(/[ぁ-ゖ]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) + 0x60))
      .replace(/[\s・･\-‐－ー―~〜「」『』【】\[\]()（）<>＜＞!！?？、。,.:：/／★☆◆◇#＃]/g, (ch) =>
        // 長音「ー」はカード名の一部なので残す
        ch === "ー" ? ch : "",
      );
  }

  // セット略号(「M4」「M-P」等)は短く他の語に埋もれやすいので、英数字の境界つきで探す
  function setIdPattern(id) {
    const body = id
      .replace(/[^a-z0-9]/gi, "")
      .split("")
      .join("[-\\s]?");
    return new RegExp(`(?:^|[^a-z0-9])${body}(?:[^a-z0-9]|$)`, "i");
  }

  // セット名の照合キー。出品タイトルでは「ポケモンカード151」→「151」、
  // 「テラスタルフェスex」→「テラスタルフェス」のように略されることが多いので略称も持つ
  function setNameKeys(name) {
    const full = normalize(name);
    const short = full.replace(/^ポケモンカード/, "").replace(/ex$/, "");
    return [...new Set([full, short])].filter((k) => k.length >= 3);
  }

  const padNo = (n) => String(Number(n)).padStart(3, "0");

  // 価格データから照合用インデックスを作る(取得のたびに1回だけ)
  function buildIndex(data) {
    if (!data || data.v !== FORMAT_VERSION || !data.available) return null;
    const setNames = new Map(data.sets.map((s) => [s.id, s.name]));
    const byName = new Map();
    for (const [setId, localId, name, eur, avg7, avg30] of data.cards) {
      const key = normalize(name);
      if (key.length < MIN_NAME_LENGTH) continue;
      const card = {
        setId,
        setName: setNames.get(setId) ?? setId,
        localId,
        name,
        eur,
        avg7,
        avg30,
      };
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key).push(card);
    }
    // 長い名前から照合する(「メガゲッコウガex」を「ゲッコウガ」より優先)
    const names = [...byName.keys()].sort((a, b) => b.length - a.length);
    return {
      eurJpy: data.eurJpy,
      fetchedAt: data.fetchedAt,
      byName,
      names,
      sets: data.sets.map((s) => ({
        id: s.id,
        idRe: setIdPattern(s.id),
        nameKeys: setNameKeys(s.name),
      })),
    };
  }

  // タイトル中のカード番号(例: 「081/080」「No.081」)を抜き出す
  function extractNumbers(title) {
    const t = String(title ?? "").normalize("NFKC");
    const nums = new Set();
    for (const m of t.matchAll(/(\d{1,3})\s*\/\s*(\d{2,3}|[a-z]+-?p)/gi)) nums.add(padNo(m[1]));
    for (const m of t.matchAll(/no\.?\s*(\d{1,3})\b/gi)) nums.add(padNo(m[1]));
    return nums;
  }

  // ポケカの出品らしいか(ぬいぐるみ等の同名グッズに相場を出さないため)。
  // 「ポケカ」等の語、カード番号、監視セット名のいずれかがあれば対象とする。
  // サプライ・未開封BOX等は対象外
  const CARD_WORDS = ["ポケカ", "ポケモンカード", "pokemoncard", "pokemontcg"];
  // シングルカードの相場を出すと誤解を招く出品(サプライ・未開封品・オリパ)
  const NG_WORDS = [
    "スリーブ",
    "デッキシールド",
    "プレイマット",
    "ラバーマット",
    "デッキケース",
    "ローダー",
    "ストレージ",
    "バインダー",
    "カードファイル",
    "box",
    "ボックス",
    "パック",
    "オリパ",
    "未開封",
  ];
  function isCardListing(index, title) {
    const text = normalize(title);
    if (NG_WORDS.some((w) => text.includes(w))) return false;
    if (CARD_WORDS.some((w) => text.includes(w))) return true;
    if (extractNumbers(title).size > 0) return true;
    return index.sets.some((s) => s.nameKeys.some((k) => text.includes(k)));
  }

  // タイトルから該当カード候補を探す。
  // 戻り値: null(該当なし・まとめ売り)または [{ name, cards, exact }]
  function match(index, title) {
    if (!index) return null;
    const text = normalize(title);
    if (!text || !isCardListing(index, title)) return null;

    // 長い名前から順に照合し、既に採用した範囲に含まれる短い名前は捨てる
    const taken = [];
    const hits = [];
    for (const key of index.names) {
      let from = 0;
      let pos;
      while ((pos = text.indexOf(key, from)) !== -1) {
        const end = pos + key.length;
        const overlaps = taken.some(([s, e]) => pos < e && end > s);
        if (!overlaps) {
          taken.push([pos, end]);
          if (!hits.includes(key)) hits.push(key);
        }
        from = pos + 1;
      }
    }
    if (hits.length === 0 || hits.length > MAX_DISTINCT_NAMES) return null;

    const numbers = extractNumbers(title);
    const plain = String(title).normalize("NFKC");
    const setHits = index.sets.filter(
      (s) => s.idRe.test(plain) || s.nameKeys.some((k) => text.includes(k)),
    );

    const results = [];
    for (const key of hits) {
      let cards = index.byName.get(key);
      // セット指定があれば絞り込む。指定セットに無いカードは監視外のセットの同名カードなので、
      // 別セットの価格を出さないよう候補から外す(例: 監視外セットの「ルチア SR」)
      if (setHits.length > 0) {
        cards = cards.filter((c) => setHits.some((s) => s.id === c.setId));
        if (cards.length === 0) continue;
      }
      // 番号で絞り込む(番号が一致しない場合は表記揺れもあるので絞り込まずに残す)
      const byNo = cards.filter((c) => numbers.has(padNo(c.localId)));
      if (byNo.length > 0) cards = byNo;
      cards = [...cards].sort((a, b) => b.eur - a.eur);
      results.push({ name: cards[0].name, cards, exact: cards.length === 1 });
    }
    return results.length > 0 ? results : null;
  }

  const toJpy = (index, eur) => (eur == null ? null : Math.round(eur * index.eurJpy));

  // 直近価格の7日平均比(%)。7日平均が無ければnull
  const change7d = (card) =>
    card.avg7 ? Math.round(((card.eur - card.avg7) / card.avg7) * 1000) / 10 : null;

  globalThis.PokecaMatcher = {
    FORMAT_VERSION,
    normalize,
    buildIndex,
    extractNumbers,
    isCardListing,
    match,
    toJpy,
    change7d,
  };
})();
