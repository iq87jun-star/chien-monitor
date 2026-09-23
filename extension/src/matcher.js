// 商品タイトルとカード価格データの突き合わせ(純粋関数のみ・DOM非依存)。
// content script(クラシックスクリプト)と node:test の両方から読み込むため、
// export は使わず globalThis.PokecaMatcher に公開する。
// データ形式は toreca/pipeline/export-ext.mjs・export-onepiece.mjs と duel/pipeline/export-ext.mjs
// (v1)と対応。
// 1つの価格データ(=1ゲーム)ごとにインデックスを作り、ゲームごとに照合する。
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

  // データ側で指定できる表示・判定用の項目だけを取り出す
  const pick = (data) =>
    Object.fromEntries(
      ["game", "label", "source", "currency", "siteUrl", "keywords", "disclaimer"]
        .filter((k) => data[k] !== undefined)
        .map((k) => [k, data[k]]),
    );

  // ゲームごとの既定値。ポケカのデータ(v1初版)はこれらの項目を持たないためここで補う
  const POKECA_DEFAULTS = {
    game: "pokeca",
    label: "日本語版",
    source: "Cardmarket",
    currency: "EUR",
    siteUrl: "https://pokeca-kaigai.com/",
    keywords: ["ポケカ", "ポケモンカード", "pokemoncard", "pokemontcg"],
    disclaimer: "欧州の取引平均を円換算した参考値です",
  };

  // 価格データから照合用インデックスを作る(取得のたびに1回だけ)。
  // カード行: [setId, localId, 名前(文字列、または別名の配列で先頭が表示名), 価格, avg7, avg30,
  //            補足, 版]。価格の通貨はデータの currency(既定はEUR)
  // matchBy: "code" のデータ(ワンピース)は名前ではなく localId(カード番号)で照合する
  function buildIndex(data) {
    if (!data || data.v !== FORMAT_VERSION || !data.available) return null;
    const meta = { ...POKECA_DEFAULTS, ...pick(data) };
    const byCode = data.matchBy === "code" ? new Map() : null;
    const variantLabels = data.variantLabels ?? {};
    const setNames = new Map(data.sets.map((s) => [s.id, s.name]));
    const byName = new Map();
    for (const [setId, localId, nameOrNames, price, avg7, avg30, note, variant] of data.cards) {
      const names = Array.isArray(nameOrNames) ? nameOrNames : [nameOrNames];
      const card = {
        setId,
        setName: setNames.get(setId) ?? setId,
        localId,
        name: names[0],
        price,
        avg7,
        avg30,
        note: note ?? null,
        variant: variant ?? null,
        variantLabel: variant ? (variantLabels[variant] ?? variant) : null,
      };
      if (byCode) {
        if (!byCode.has(localId)) byCode.set(localId, []);
        byCode.get(localId).push(card);
        continue;
      }
      for (const key of new Set(names.map(normalize))) {
        if (key.length < MIN_NAME_LENGTH) continue;
        if (!byName.has(key)) byName.set(key, []);
        byName.get(key).push(card);
      }
    }
    // 長い名前から照合する(「メガゲッコウガex」を「ゲッコウガ」より優先)
    const names = [...byName.keys()].sort((a, b) => b.length - a.length);
    return {
      ...meta,
      keywords: meta.keywords.map(normalize),
      codeRe: data.codePattern ? new RegExp(data.codePattern, "i") : null,
      codeReAll: data.codePattern ? new RegExp(data.codePattern, "gi") : null,
      byCode,
      variantRules: (data.variantRules ?? []).map(([tag, re]) => [tag, new RegExp(re, "i")]),
      defaultVariant: data.defaultVariant ?? null,
      // 1通貨単位あたりの円(ポケカ・遊戯王はEUR建ての eurJpy、ワンピースはUSD建ての rateJpy)
      rateJpy: data.rateJpy ?? data.eurJpy,
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

  // そのゲームの出品らしいか(ぬいぐるみ等の同名グッズや他ゲームの出品に相場を出さないため)。
  // ゲームの語(「ポケカ」「遊戯王」等)、カード番号、監視セット名のいずれかがあれば対象とする。
  // サプライ・未開封BOX等は対象外
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
    "まとめ売り",
    "オリパ",
    "未開封",
    "ストラクチャーデッキ",
  ];
  // タイトルと同じ正規化をかけておく(「まとめ売り」→「マトメ売リ」)
  const NG_KEYS = NG_WORDS.map(normalize);
  function isCardListing(index, title) {
    const text = normalize(title);
    if (NG_KEYS.some((w) => text.includes(w))) return false;
    if (index.keywords.some((w) => text.includes(w))) return true;
    if (index.codeRe?.test(String(title).normalize("NFKC"))) return true;
    // 型番(081/080)・セット名での判定はセット情報を持つデータ(ポケカ)だけ
    if (index.sets.length === 0) return false;
    if (extractNumbers(title).size > 0) return true;
    return index.sets.some((s) => s.nameKeys.some((k) => text.includes(k)));
  }

  // カード番号で照合する(ワンピース)。タイトルの語(パラレル・コミパラ・SP等)で版を選び、
  // 版の語が無ければ通常版とみなす。指定の版がデータに無ければ全版を候補にする
  function matchByCode(index, title) {
    const plain = String(title).normalize("NFKC");
    const codes = [...new Set([...plain.matchAll(index.codeReAll)].map((m) => m[0].toUpperCase()))];
    if (codes.length === 0 || codes.length > MAX_DISTINCT_NAMES) return null;
    const lower = plain.toLowerCase();
    const wanted = index.variantRules.find(([, re]) => re.test(lower))?.[0] ?? index.defaultVariant;
    const results = [];
    for (const code of codes) {
      const all = index.byCode.get(code);
      if (!all) continue;
      const same = all.filter((c) => c.variant === wanted);
      const cards = [...(same.length > 0 ? same : all)].sort((a, b) => b.price - a.price);
      results.push({ name: `${code} ${cards[0].name}`, cards, exact: cards.length === 1 });
    }
    return results.length > 0 ? results : null;
  }

  // タイトルから該当カード候補を探す。
  // 戻り値: null(該当なし・まとめ売り)または [{ name, cards, exact }]
  function match(index, title) {
    if (!index) return null;
    const text = normalize(title);
    if (!text || !isCardListing(index, title)) return null;
    if (index.byCode) return matchByCode(index, title);

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
      cards = [...cards].sort((a, b) => b.price - a.price);
      // 別名(漢字名と読み仮名)が両方タイトルにある場合の重複を除く
      if (results.some((r) => r.cards[0] === cards[0])) continue;
      results.push({ name: cards[0].name, cards, exact: cards.length === 1 });
    }
    return results.length > 0 ? results : null;
  }

  const toJpy = (index, price) => (price == null ? null : Math.round(price * index.rateJpy));

  // 直近価格の7日平均比(%)。7日平均が無ければnull
  const change7d = (card) =>
    card.avg7 ? Math.round(((card.price - card.avg7) / card.avg7) * 1000) / 10 : null;

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
