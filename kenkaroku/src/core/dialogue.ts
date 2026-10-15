import { BANTERS, VOICES, type Banter, type TimeOfDay } from "../data/voices";

/** 朝 5〜10時・昼 10〜17時・夜 それ以外 */
export function timeOfDay(d: Date): TimeOfDay {
  const h = d.getHours();
  if (h >= 5 && h < 10) return "morning";
  if (h >= 10 && h < 17) return "day";
  return "night";
}

/** ホームでタップしたときの台詞候補（共通＋時間帯限定） */
export function homeLines(charId: string, tod: TimeOfDay): string[] {
  const v = VOICES[charId];
  return v ? [...v.home, v.homeTime[tod]] : [];
}

/** 編成リーダーと所持キャラで成立する掛け合い */
export function availableBanters(leader: string | null, owned: Iterable<string>): Banter[] {
  if (!leader) return [];
  const have = new Set(owned);
  return BANTERS.filter((b) => b.leader === leader && have.has(b.partner));
}

/** 編成の先頭（前列左から）をリーダーとする */
export function teamLeader(team: (string | null)[]): string | null {
  return team.find((id): id is string => !!id) ?? null;
}
