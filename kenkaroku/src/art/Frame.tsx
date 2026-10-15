// レア枠。URは金の二重枠と金継ぎのひび、SSRは紫、SRは青。
import type { Rarity } from "../core/types";

export function RarityFrame({ rarity, color }: { rarity: Rarity; color: string }) {
  const corner = (x: number, y: number, sx: number, sy: number) => (
    <path
      key={`${x}${y}`}
      d="M0 28 L0 0 L28 0 M8 20 L8 8 L20 8"
      fill="none"
      stroke={color}
      strokeWidth="3"
      transform={`translate(${x} ${y}) scale(${sx} ${sy})`}
    />
  );
  return (
    <g pointerEvents="none">
      <rect x="3" y="3" width="294" height="394" rx="6" fill="none" stroke={color} strokeWidth={rarity === "SR" ? 3 : 4} />
      {rarity !== "SR" && <rect x="10" y="10" width="280" height="380" rx="3" fill="none" stroke={color} strokeWidth="1" opacity=".6" />}
      {corner(8, 8, 1, 1)}
      {corner(292, 8, -1, 1)}
      {corner(8, 392, 1, -1)}
      {corner(292, 392, -1, -1)}
      {rarity === "UR" && (
        <g stroke="#f2dc94" strokeWidth="1.6" fill="none" opacity=".9">
          <path d="M3 96 L22 104 L30 92 L52 100 L60 96" />
          <path d="M22 104 L26 122" />
          <path d="M297 300 L276 296 L268 308 L246 302 L238 310" />
          <path d="M268 308 L272 330" />
        </g>
      )}
    </g>
  );
}
