import { CHAR_BY_ID } from "../../data/characters";
import type { OwnedState } from "../../core/game";
import { rarityColor } from "../theme/tokens";
import { BloomPips, ElementBadge, RoleBadge } from "./Badges";
import { Portrait } from "./Portrait";

/** 一覧用の小さなカード */
export function CharCard({
  id,
  owned,
  onClick,
  selected,
  note,
}: {
  id: string;
  owned?: OwnedState;
  onClick?: () => void;
  selected?: boolean;
  note?: string;
}) {
  const c = CHAR_BY_ID[id];
  return (
    <button
      className={`k-card ${selected ? "is-selected" : ""} ${owned ? "" : "is-locked"}`}
      style={{ ["--rc" as string]: rarityColor(c.rarity) }}
      onClick={onClick}
    >
      <div className="k-card__art">
        <Portrait id={id} crop="bust" dim={!owned} />
        <span className="k-card__rarity">{c.rarity}</span>
        {note && <span className="k-card__note">{note}</span>}
      </div>
      <div className="k-card__meta">
        <div className="k-card__name">{c.given}</div>
        <div className="k-card__badges">
          <ElementBadge element={c.element} />
          <RoleBadge role={c.role} />
          {owned && <span className="k-card__lv num">Lv{owned.level}</span>}
        </div>
        {owned && <BloomPips star={owned.star} size={7} />}
      </div>
    </button>
  );
}
