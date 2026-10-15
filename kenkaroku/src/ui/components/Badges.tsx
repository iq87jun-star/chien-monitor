import { ELEMENT_LABEL, ROLE_LABEL, type Element, type Rarity, type Role } from "../../core/types";
import { bloomStageName } from "../../core/economy";
import { elementColor, rarityColor } from "../theme/tokens";

export function RarityBadge({ rarity }: { rarity: Rarity }) {
  return (
    <span className="k-badge k-badge--rarity" style={{ color: rarityColor(rarity), borderColor: rarityColor(rarity) }}>
      {rarity}
    </span>
  );
}

export function ElementBadge({ element }: { element: Element }) {
  return (
    <span className="k-badge k-badge--el" style={{ background: elementColor(element) }}>
      {ELEMENT_LABEL[element]}
    </span>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  return <span className="k-badge k-badge--role">{ROLE_LABEL[role]}</span>;
}

/** 花の段階（★）表示。満開まで10枚の花びらで表す */
export function BloomPips({ star, size = 10 }: { star: number; size?: number }) {
  return (
    <span className="k-bloom" title={`${bloomStageName(star)}（★${star}）`} aria-label={`${bloomStageName(star)}`}>
      {Array.from({ length: 10 }, (_, i) => (
        <svg key={i} width={size} height={size} viewBox="0 0 10 10" aria-hidden>
          <path
            d="M5 0.6 C6.6 2.4 6.6 4.2 5 5.6 C3.4 4.2 3.4 2.4 5 0.6 Z"
            transform="rotate(0 5 5)"
            fill={i < star ? "var(--k-kin)" : "none"}
            stroke={i < star ? "var(--k-kinLight)" : "var(--k-washiFaint)"}
            strokeWidth="0.7"
          />
          <circle cx="5" cy="7.4" r="1.4" fill={i < star ? "var(--k-shu)" : "none"} stroke="var(--k-washiFaint)" strokeWidth={i < star ? 0 : 0.5} />
        </svg>
      ))}
    </span>
  );
}
