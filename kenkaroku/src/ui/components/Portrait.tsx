import { CHAR_BY_ID } from "../../data/characters";
import { ENEMY_BY_ID } from "../../data/enemies";
import { elementColor, rarityColor } from "../theme/tokens";

export type PortraitCrop = "full" | "bust" | "face";

const VIEWBOX: Record<PortraitCrop, string> = {
  full: "0 0 300 400",
  bust: "40 20 220 220",
  face: "85 40 130 130",
};

/**
 * 剣華の立ち絵。imageUrl があれば画像、無ければ仮のSVGを描く。
 */
export function Portrait({
  id,
  crop = "full",
  className = "",
  dim = false,
}: {
  id: string;
  crop?: PortraitCrop;
  className?: string;
  dim?: boolean;
}) {
  const c = CHAR_BY_ID[id];
  if (!c) return null;
  if (c.imageUrl) {
    return <img className={`k-portrait ${className}`} src={c.imageUrl} alt={c.given} style={{ filter: dim ? "grayscale(1) brightness(.5)" : undefined }} />;
  }
  const el = elementColor(c.element);
  return (
    <svg
      className={`k-portrait ${className}`}
      viewBox={VIEWBOX[crop]}
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label={c.given}
      style={{ filter: dim ? "grayscale(1) brightness(.45)" : undefined }}
    >
      <rect x="0" y="0" width="300" height="400" fill={el} opacity=".35" />
      <text x="150" y="190" textAnchor="middle" fontSize="140" fill={c.color} fontFamily="var(--k-font-brush)">
        {c.given[0]}
      </text>
      <rect x="2" y="2" width="296" height="396" fill="none" stroke={rarityColor(c.rarity)} strokeWidth="4" />
    </svg>
  );
}

export function EnemyPortrait({ id, className = "" }: { id: string; className?: string }) {
  const e = ENEMY_BY_ID[id];
  if (!e) return null;
  return (
    <svg className={`k-portrait ${className}`} viewBox="0 0 100 100" role="img" aria-label={e.name}>
      <rect width="100" height="100" fill={elementColor(e.element)} opacity=".3" />
      <text x="50" y="68" textAnchor="middle" fontSize="54" fill="var(--k-washi)" fontFamily="var(--k-font-brush)">
        {e.glyph}
      </text>
    </svg>
  );
}
