import type { GachaPool } from "../core/gacha";
import { CHARACTERS } from "./characters";

export interface BannerDef {
  id: string;
  title: string;
  lead: string;
  pickup: string;
}

/** 開催中の花結び。ピックアップを変えるときはここを書き換える */
export const CURRENT_BANNER: BannerDef = {
  id: "b-hisame-01",
  title: "血桜、夜に咲く",
  lead: "紅葉 緋雨 の出現率アップ中",
  pickup: "hisame",
};

export function bannerPool(b: BannerDef): GachaPool {
  const ids = (r: string) => CHARACTERS.filter((c) => c.rarity === r).map((c) => c.id);
  return { pickup: b.pickup, ur: ids("UR"), ssr: ids("SSR"), sr: ids("SR") };
}
