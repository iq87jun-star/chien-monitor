// 価格差リストの計算(純粋関数のみ・通信なし)。run.mjs と node:test の両方から使う。
// 海外相場(toreca の Cardmarket 価格)と、楽天市場の国内出品を突き合わせ、
// 「国内で買って海外で売ったら手元にいくら残るか」を出す。
import "../../extension/src/matcher.js";

const M = globalThis.PokecaMatcher;

// 国内出品のうち、このカードの単品の相場として使えないもの
// (鑑定品は値段の付き方が別物・海外版は別のカード・まとめ売りやオリパは単価が出せない)
const NG_RE =
  /PSA|BGS|CGC|ARS|鑑定|英語版|海外版|韓国版|中国版|簡体字|繁体字|まとめ|セット売り|オリパ|くじ|ジャンク|傷あり|キズあり|プレイ用|未開封|box|ボックス|パック|スリーブ|ローダー/i;

const padNo = (n) => String(Number(n)).padStart(3, "0");

// 海外相場の候補カード。円換算が minJpy 以上のものを高い順に max 件
export function pickCandidates(cards, eurJpy, { minJpy, max }) {
  return cards
    .filter((c) => typeof c.eur === "number" && c.eur * eurJpy >= minJpy)
    .sort((a, b) => b.eur - a.eur)
    .slice(0, max);
}

// 楽天で探す言葉。型番の分子(例: 120)を入れて同名の別レアリティを減らす
export function searchKeyword(card) {
  return `ポケモンカード ${card.name} ${padNo(card.localId)}`;
}

// 出品タイトルがこのカードの単品出品か。カード名と型番の両方がタイトルにあるものだけ認める
// (型番が無いと、同じ名前の別レアリティ(数十倍の値段差)と区別できないため)
export function isSameCard(card, title) {
  const t = String(title ?? "");
  if (NG_RE.test(t.normalize("NFKC"))) return false;
  const name = M.normalize(card.name);
  if (name.length < 2 || !M.normalize(t).includes(name)) return false;
  return M.extractNumbers(t).has(padNo(card.localId));
}

// 楽天の検索結果(formatVersion 2 の Items)から、このカードの国内最安を出す。
// 送料別の出品は domesticShipping を足した値段で比べる
export function domesticQuote(card, items, { minListingJpy, domesticShipping }) {
  const listings = (items ?? [])
    .filter((i) => typeof i.itemPrice === "number" && i.itemPrice >= minListingJpy)
    .filter((i) => isSameCard(card, i.itemName))
    .map((i) => ({
      price: i.itemPrice,
      total: i.itemPrice + (i.postageFlag === 1 ? domesticShipping : 0),
      title: i.itemName,
      url: i.affiliateUrl || i.itemUrl,
      shop: i.shopName ?? null,
    }))
    .sort((a, b) => a.total - b.total);
  if (listings.length === 0) return null;
  return { count: listings.length, cheapest: listings[0] };
}

// 1枚あたりの手残り。海外の売値から手数料・為替の目減り・国際送料を引き、国内の仕入れ値を引く
export function profit(overseasJpy, buyJpy, { sellFeeRate, fxHaircut, intlShipping }) {
  const net = overseasJpy * (1 - sellFeeRate - fxHaircut) - intlShipping;
  const yen = Math.round(net - buyJpy);
  return { net: Math.round(net), yen, rate: buyJpy > 0 ? Math.round((yen / buyJpy) * 1000) / 10 : null };
}

// 全カードの結果を、海外で売ると得なもの(export)と、国内の方が高いもの(domesticHigh)に分ける
export function buildList(rows, settings) {
  const scored = rows
    .filter((r) => r.quote)
    .map((r) => {
      const overseasJpy = Math.round(r.card.eur * settings.eurJpy);
      const p = profit(overseasJpy, r.quote.cheapest.total, settings);
      return {
        id: r.card.id,
        name: r.card.name,
        set: r.card.set,
        setId: r.card.setId,
        localId: r.card.localId,
        rarity: r.card.rarity ?? null,
        eur: r.card.eur,
        avg7: r.card.avg7 ?? null,
        overseasJpy,
        domesticJpy: r.quote.cheapest.total,
        listings: r.quote.count,
        profitJpy: p.yen,
        profitRate: p.rate,
        url: r.quote.cheapest.url,
        shop: r.quote.cheapest.shop,
        title: r.quote.cheapest.title,
      };
    });
  const exportList = scored
    .filter((s) => s.profitJpy >= settings.minProfitJpy && s.profitRate >= settings.minProfitRate)
    .sort((a, b) => b.profitJpy - a.profitJpy);
  // 国内の方が海外の円換算より高いもの(手持ちを売るなら国内、の参考)
  const domesticHigh = scored
    .filter((s) => s.domesticJpy > s.overseasJpy)
    .map((s) => ({ ...s, gapRate: Math.round((s.domesticJpy / s.overseasJpy - 1) * 1000) / 10 }))
    .sort((a, b) => b.gapRate - a.gapRate);
  return { exportList, domesticHigh, matched: scored.length };
}

const yen = (n) => `¥${Math.round(n).toLocaleString("ja-JP")}`;

// 人が読むレポート(Markdown)
export function renderReport(result, meta) {
  const lines = [];
  lines.push(`# ポケカ 国内→海外 価格差リスト`);
  lines.push("");
  lines.push(
    `作成: ${meta.generatedAt}(日本時間) / 海外相場: Cardmarket(${meta.overseasFetchedAt} 取得)` +
      ` / 為替 1€ = ${meta.eurJpy}円`,
  );
  lines.push(
    `調べたカード ${meta.searched} 枚のうち、楽天で同じカードの出品が見つかったのは ${result.matched} 枚。`,
  );
  lines.push("");
  lines.push(
    `手残りの計算: 海外の売値 × (1 − 手数料 ${meta.sellFeeRate * 100}% − 為替の目減り ${meta.fxHaircut * 100}%)` +
      ` − 国際送料 ${yen(meta.intlShipping)} − 国内の仕入れ値(送料別の出品は +${yen(meta.domesticShipping)})`,
  );
  lines.push("");
  lines.push(`## 海外で売ると得なカード(手残り ${yen(meta.minProfitJpy)} 以上・${meta.minProfitRate}% 以上)`);
  lines.push("");
  if (result.exportList.length === 0) {
    lines.push("今日は条件に合うカードがありません。");
  } else {
    lines.push("| カード | セット | 海外相場 | 国内最安 | 手残り | 利益率 | 国内出品 |");
    lines.push("|---|---|---:|---:|---:|---:|---|");
    for (const s of result.exportList.slice(0, meta.maxRows)) {
      lines.push(
        `| ${s.name} ${s.localId} | ${s.set} | ${yen(s.overseasJpy)} | ${yen(s.domesticJpy)} | ` +
          `${yen(s.profitJpy)} | ${s.profitRate}% | [${s.shop ?? "楽天"}](${s.url}) |`,
      );
    }
  }
  lines.push("");
  lines.push(`## 国内の方が高いカード(手持ちを売るなら国内)`);
  lines.push("");
  if (result.domesticHigh.length === 0) {
    lines.push("該当なし。");
  } else {
    lines.push("| カード | セット | 海外相場 | 国内最安 | 国内が高い割合 |");
    lines.push("|---|---|---:|---:|---:|");
    for (const s of result.domesticHigh.slice(0, 10)) {
      lines.push(
        `| ${s.name} ${s.localId} | ${s.set} | ${yen(s.overseasJpy)} | ${yen(s.domesticJpy)} | +${s.gapRate}% |`,
      );
    }
  }
  lines.push("");
  lines.push("## 注意");
  lines.push("");
  lines.push(
    "- 海外相場は Cardmarket(欧州)の取引平均で、日本から出品できる eBay 等の実際の売値とは差があります。" +
      "仕入れる前に eBay の売れた価格(Sold)で必ず確かめてください。",
  );
  lines.push("- 国内最安は楽天の出品価格です。状態(美品・傷あり)や在庫は出品ページで確かめてください。");
  lines.push("- 型番まで一致した出品だけを比べていますが、取り違えがないか最後は目で確かめてください。");
  lines.push("- 売買の助言ではありません。少ない枚数で試してから広げてください。");
  return lines.join("\n") + "\n";
}

// Discord に送る文(1通 2,000 字まで)
export function discordMessages(result, meta) {
  const head =
    `**ポケカ 国内→海外 価格差リスト**(${meta.generatedAt})\n` +
    `海外で売ると得なカード ${result.exportList.length} 枚` +
    (result.exportList.length > 0 ? "(手残りの多い順)" : "");
  const rows = result.exportList
    .slice(0, 10)
    .map(
      (s) =>
        `・${s.name} ${s.localId}(${s.set}) 海外 ${yen(s.overseasJpy)} / 国内 ${yen(s.domesticJpy)}` +
        ` → 手残り ${yen(s.profitJpy)}(${s.profitRate}%)\n  <${s.url}>`,
    );
  const messages = [];
  let current = head;
  for (const row of rows) {
    if ((current + "\n" + row).length > 1900) {
      messages.push(current);
      current = row;
    } else {
      current += "\n" + row;
    }
  }
  messages.push(current);
  return messages;
}
