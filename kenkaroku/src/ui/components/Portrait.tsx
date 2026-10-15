import { useId } from "react";
import { CHAR_BY_ID, type CharacterDef } from "../../data/characters";
import { ENEMY_BY_ID } from "../../data/enemies";
import { elementColor, rarityColor, TOKENS } from "../theme/tokens";
import { ElementPattern } from "../../art/patterns";
import { Motif } from "../../art/motifs";
import { Body, hair, weapon } from "../../art/silhouette";
import { RarityFrame } from "../../art/Frame";

export type PortraitCrop = "full" | "bust" | "face";

const VIEWBOX: Record<PortraitCrop, string> = {
  full: "0 0 300 400",
  bust: "50 52 200 200",
  face: "100 92 100 100",
};

const SIL = "#130d0c"; // シルエットの墨色
const FACE = "#3b2d27";

/**
 * 剣華の立ち絵。imageUrl があれば画像、無ければ SVG のレイヤー構成で描く：
 * 背景（属性の和柄）→ シルエット（髪型・武器）→ モチーフ紋 → レア枠
 */
export function Portrait({
  id,
  crop = "full",
  className = "",
  dim = false,
  frame = crop === "full",
  background = true,
}: {
  id: string;
  crop?: PortraitCrop;
  className?: string;
  dim?: boolean;
  frame?: boolean;
  /** false にすると和柄の背景を描かない（ホームの情景に立たせるとき） */
  background?: boolean;
}) {
  const c = CHAR_BY_ID[id];
  if (!c) return null;
  const style = { filter: dim ? "grayscale(1) brightness(.45)" : undefined };
  if (c.imageUrl) {
    return <img className={`k-portrait ${className}`} src={c.imageUrl} alt={c.given} style={style} />;
  }
  return (
    <svg className={`k-portrait ${className}`} viewBox={VIEWBOX[crop]} preserveAspectRatio="xMidYMid slice" role="img" aria-label={c.given} style={style}>
      <PortraitLayers c={c} frame={frame} background={background} />
    </svg>
  );
}

function PortraitLayers({ c, frame, background }: { c: CharacterDef; frame: boolean; background: boolean }) {
  const uid = useId().replace(/:/g, "");
  const el = elementColor(c.element);
  const h = hair(c.hair, c.colorSub);
  const w = weapon(c.weaponShape, c.color, c.colorSub);
  return (
    <>
      <defs>
        <radialGradient id={`bg${uid}`} cx="50%" cy="35%" r="75%">
          <stop offset="0" stopColor={el} stopOpacity=".55" />
          <stop offset="1" stopColor={TOKENS.color.sumi} />
        </radialGradient>
        <ElementPattern id={`pt${uid}`} element={c.element} color={el} />
        <linearGradient id={`fade${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset=".72" stopColor={TOKENS.color.sumi} stopOpacity="0" />
          <stop offset="1" stopColor={TOKENS.color.sumi} stopOpacity=".85" />
        </linearGradient>
      </defs>

      {/* 1. 背景：属性色の和柄 */}
      {background && (
        <>
          <rect width="300" height="400" fill={`url(#bg${uid})`} />
          <rect width="300" height="400" fill={`url(#pt${uid})`} />
        </>
      )}
      <circle cx="150" cy="150" r="112" fill={c.color} opacity=".22" />
      <circle cx="150" cy="150" r="112" fill="none" stroke={c.color} strokeWidth="1.5" opacity=".6" />
      <g transform="translate(176 18) scale(1.15)" opacity=".28">
        <Motif motif={c.motif} color={c.color} accent={c.colorSub} />
      </g>

      {/* 2. シルエット：武器（後ろ）→ 髪（後ろ）→ 体 → 顔 → 前髪 → 武器（前） */}
      <g fill={SIL} stroke={c.color} strokeWidth="2.2" strokeLinejoin="round">
        {w.back}
        {h.back}
        <Body color={c.color} sub={c.colorSub} />
      </g>
      <ellipse cx="150" cy="144" rx="31" ry="35" fill={FACE} />
      <g stroke={SIL} strokeWidth="2.6" fill="none" strokeLinecap="round">
        <path d="M132 150 q6 -4 12 0 M156 150 q6 -4 12 0" />
      </g>
      <g fill={SIL} stroke={c.color} strokeWidth="2.2" strokeLinejoin="round">
        {h.front}
      </g>
      <g strokeLinejoin="round">{w.front}</g>

      {/* 3. モチーフ紋（胸元） */}
      <g transform="translate(130 268) scale(.4)">
        <circle cx="50" cy="50" r="48" fill={SIL} stroke={c.colorSub} strokeWidth="4" />
        <g transform="translate(14 14) scale(.72)">
          <Motif motif={c.motif} color={c.color} accent={c.colorSub} />
        </g>
      </g>

      {background && <rect width="300" height="400" fill={`url(#fade${uid})`} />}
      {/* 4. レア枠 */}
      {frame && <RarityFrame rarity={c.rarity} color={rarityColor(c.rarity)} />}
    </>
  );
}

export function EnemyPortrait({ id, className = "" }: { id: string; className?: string }) {
  const e = ENEMY_BY_ID[id];
  const uid = useId().replace(/:/g, "");
  if (!e) return null;
  const el = elementColor(e.element);
  return (
    <svg className={`k-portrait ${className}`} viewBox="0 0 100 100" role="img" aria-label={e.name}>
      <defs>
        <radialGradient id={`eg${uid}`} cx="50%" cy="40%" r="70%">
          <stop offset="0" stopColor={el} stopOpacity=".5" />
          <stop offset="1" stopColor="#0a0707" />
        </radialGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#eg${uid})`} />
      {/* 角 */}
      <path d="M28 30 L20 6 L38 24 Z M72 30 L80 6 L62 24 Z" fill="#d9d0c0" opacity={e.boss ? 1 : 0.7} />
      <text x="50" y="72" textAnchor="middle" fontSize="50" fill={e.boss ? "#f2dc94" : "#f3ead8"} fontFamily="var(--k-font-brush)">
        {e.glyph}
      </text>
      {e.boss && <rect x="2" y="2" width="96" height="96" fill="none" stroke="#d4462c" strokeWidth="3" />}
    </svg>
  );
}
