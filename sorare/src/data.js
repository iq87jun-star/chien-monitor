// データ取得(クラブの日程・成績、選手の成績と最安値、自分のカード)。どれも run.js から呼ぶ。
import { usd } from "./api.js";
import { startRate } from "./model.js";

const PRICE = "slug liveSingleSaleOffer { receiverSide { amounts { usdCents eurCents wei } } }";

// 対象の節は次の節(UPCOMING)。SORARE_FIXTURE に節の slug を入れるとその節にする(先の節を試す時用)
export async function upcoming(gql, leaderboardSuffix) {
  const fx = process.env.SORARE_FIXTURE
    ? (await gql("query($s: String!) { so5 { so5Fixture(slug: $s) { slug startDate } } }", { s: process.env.SORARE_FIXTURE })).so5.so5Fixture
    : (await gql("{ so5 { so5Fixture(type: UPCOMING) { slug startDate } } }")).so5.so5Fixture;
  const slug = `${fx.slug}-${leaderboardSuffix}`;
  let lb = null;
  try { lb = (await gql("query($s: String!) { so5 { so5Leaderboard(slug: $s) { id displayName } } }", { s: slug }, { retries: 1 })).so5.so5Leaderboard; } catch { /* その節にこの大会が無い */ }
  return { fixture: fx, leaderboardSlug: slug, leaderboard: lb };
}

export async function clubs(gql, competition) {
  const list = (await gql("query($c: String!) { football { competition(slug: $c) { clubs(first: 40) { nodes { slug name } } } } }", { c: competition })).football.competition.clubs.nodes;
  const out = [];
  for (const c of list) {
    const d = (await gql(`query($s: String!) { football { club(slug: $s) { name
      upcomingGames(first: 1) { date homeTeam { name } awayTeam { name } }
      latestGames(first: 10) { nodes { homeGoals awayGoals homeTeam { name } awayTeam { name } } }
      activePlayers(first: 80) { nodes { slug } } } } }`, { s: c.slug })).football.club;
    out.push({ slug: c.slug, name: d.name, next: d.upcomingGames[0] || null, games: d.latestGames.nodes, players: d.activePlayers.nodes.map((n) => n.slug) });
  }
  return out;
}

export async function player(gql, slug, rarity) {
  const p = (await gql(`query($s: String!) { anyPlayer(slug: $s) { ... on Player { slug displayName age position
    averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
    so5Scores(last: 10) { score playerGameStats { minsPlayed } }
    activeClub { name domesticLeague { slug } }
    lowestPriceAnyCard(rarity: ${rarity}, inSeason: true) { ${PRICE} } } } }`, { s: slug })).anyPlayer;
  if (!p) return null;
  return {
    id: p.slug, name: p.displayName, age: p.age, pos: p.position, l15: p.averageScore || 0,
    start: startRate(p.so5Scores), club: p.activeClub?.name, league: p.activeClub?.domesticLeague?.slug,
    price: usd(p.lowestPriceAnyCard?.liveSingleSaleOffer?.receiverSide?.amounts), priceCard: p.lowestPriceAnyCard?.slug || null,
  };
}

export async function myCards(gql, rarity) {
  const out = [];
  let after = null;
  for (;;) {
    const d = (await gql(`query($a: String) { currentUser { cards(first: 10, after: $a, rarities: [${rarity}], sport: FOOTBALL) {
      nodes { slug rarityTyped seasonYear anyPlayer { slug } ownershipHistory { from amounts { usdCents eurCents wei } } } pageInfo { endCursor hasNextPage } } } }`, { a: after })).currentUser;
    if (!d) throw new Error("ログインしていない");
    // 1 ページ 10 枚(所有履歴まで取ると、未ログイン・APIKEY なしの上限 complexity 500 に 50 枚では収まらない)
    // 買値 = 所有履歴の最後(今の持ち主になった時)の取引額。パックなど価格の無い入手は null
    out.push(...d.cards.nodes.map((n) => ({ slug: n.slug, seasonYear: n.seasonYear, player: n.anyPlayer?.slug, cost: usd(n.ownershipHistory?.at(-1)?.amounts), since: n.ownershipHistory?.at(-1)?.from || null })));
    if (!d.cards.pageInfo.hasNextPage) return out;
    after = d.cards.pageInfo.endCursor;
  }
}

// appearances の index は GK=0, DF=1, MF=2, FW=3, エクストラ=4(bestLineup の並び)
export async function submitLineup(gql, leaderboardId, lineup, captainCard) {
  const so5Appearances = lineup.map((c, index) => ({ cardSlug: c.card, captain: c.card === captainCard, index }));
  const d = (await gql(`mutation($input: createOrUpdateSo5LineupInput!) { createOrUpdateSo5Lineup(input: $input) { so5Lineup { id } errors { message } } }`,
    { input: { so5LeaderboardId: leaderboardId, so5Appearances } }, { retries: 0 })).createOrUpdateSo5Lineup;
  if (d.errors?.length) throw new Error("ラインナップ登録エラー: " + d.errors.map((e) => e.message).join(" / "));
  return d.so5Lineup?.id;
}
