// データ取得(クラブの日程・成績、選手の成績と最安値、自分のカード)。どれも run.js から呼ぶ。
import { usd } from "./api.js";
import { startRate } from "./model.js";

const PRICE = "slug liveSingleSaleOffer { receiverSide { amounts { usdCents eurCents wei } } }";

// 対象の節は次の節(UPCOMING)。sport は FOOTBALL か NBA。SORARE_FIXTURE に節の slug を入れるとその節にする(先の節を試す時用。その競技の節だけ)
// 大会のルール(rules)も読む: captain はキャプテンの有無、averageScores は NBA の星の合計の上限(max)
export async function upcoming(gql, leaderboardSuffix, sport = "FOOTBALL") {
  const forced = process.env.SORARE_FIXTURE;
  const fx = forced && forced.startsWith(sport === "NBA" ? "nba-" : "football-")
    ? (await gql("query($s: String!) { so5 { so5Fixture(slug: $s) { slug startDate } } }", { s: forced })).so5.so5Fixture
    : (await gql(`{ so5 { so5Fixture(type: UPCOMING${sport === "NBA" ? ", sport: NBA" : ""}) { slug startDate } } }`)).so5.so5Fixture;
  const slug = `${fx.slug}-${leaderboardSuffix}`;
  let lb = null;
  try { lb = (await gql("query($s: String!) { so5 { so5Leaderboard(slug: $s) { id displayName rules { captain averageScores { max averageType } } } } }", { s: slug }, { retries: 1 })).so5.so5Leaderboard; } catch { /* その節にこの大会が無い */ }
  return { fixture: fx, leaderboardSlug: slug, leaderboard: lb };
}

// 節の中のチームごとの試合数(NBA は節の中で一番良い 1 試合が得点になるので、試合数が多いほど有利)
export async function fixtureGames(gql, fixtureSlug) {
  const games = (await gql("query($s: String!) { so5 { so5Fixture(slug: $s) { games { homeTeam { name } awayTeam { name } } } } }", { s: fixtureSlug })).so5.so5Fixture.games;
  const n = {};
  for (const g of games) for (const t of [g.homeTeam?.name, g.awayTeam?.name]) if (t) n[t] = (n[t] || 0) + 1;
  return n;
}

// NBA の選手ランク(gameplayTier)ごとの星の数。ラインナップの星の合計に上限がある
export async function nbaStars(gql) {
  const r = (await gql("{ config { gameplayTierRatings(sport: NBA) { gameplayTier stars } } }")).config.gameplayTierRatings;
  return Object.fromEntries(r.map((x) => [x.gameplayTier, x.stars]));
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

export async function nbaPlayer(gql, slug, rarity) {
  const p = (await gql(`query($s: String!) { anyPlayer(slug: $s) { ... on NBAPlayer { slug displayName age anyPositions gameplayTier
    averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE)
    playerGameScores(last: 10) { score }
    injuries { status }
    activeClub { name domesticLeague { slug } }
    lowestPriceAnyCard(rarity: ${rarity}, inSeason: true) { ${PRICE} } } } }`, { s: slug })).anyPlayer;
  if (!p) return null;
  const scores = (p.playerGameScores || []).map((g) => g.score || 0);
  return {
    id: p.slug, name: p.displayName, age: p.age, pos: (p.anyPositions?.[0] || "").replace("basketball_", ""), tier: p.gameplayTier,
    l15: p.averageScore || 0, scores, start: scores.length ? scores.filter((s) => s > 0).length / 10 : 0,
    injury: p.injuries?.[0]?.status || null, club: p.activeClub?.name, league: p.activeClub?.domesticLeague?.slug,
    price: usd(p.lowestPriceAnyCard?.liveSingleSaleOffer?.receiverSide?.amounts), priceCard: p.lowestPriceAnyCard?.slug || null,
  };
}

export async function myCards(gql, rarity, sport = "FOOTBALL") {
  const out = [];
  let after = null;
  for (;;) {
    const d = (await gql(`query($a: String) { currentUser { cards(first: 10, after: $a, rarities: [${rarity}], sport: ${sport}) {
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
