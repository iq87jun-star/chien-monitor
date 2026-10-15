import { useState } from "react";
import { CHARACTERS } from "../../data/characters";
import { ELEMENT_LABEL, type Element } from "../../core/types";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { CharCard } from "../components/CharCard";
import { Panel } from "../components/Panel";

const RARITY_ORDER = { UR: 0, SSR: 1, SR: 2 } as const;

export function Chars() {
  const roster = useGame((s) => s.save.roster);
  const open = useNav((s) => s.open);
  const [filter, setFilter] = useState<Element | "all">("all");
  const list = CHARACTERS.filter((c) => filter === "all" || c.element === filter).sort(
    (a, b) =>
      Number(!!roster[b.id]) - Number(!!roster[a.id]) ||
      RARITY_ORDER[a.rarity] - RARITY_ORDER[b.rarity] ||
      (roster[b.id]?.level ?? 0) - (roster[a.id]?.level ?? 0),
  );
  const ownedCount = CHARACTERS.filter((c) => roster[c.id]).length;
  return (
    <div className="screen chars">
      <Panel title="剣華" right={<span className="k-dim num">{ownedCount} / {CHARACTERS.length}</span>}>
        <div className="k-tabs">
          {(["all", "fire", "water", "wind", "rock"] as const).map((e) => (
            <button key={e} className={`k-tab ${filter === e ? "is-active" : ""}`} onClick={() => setFilter(e)}>
              {e === "all" ? "すべて" : ELEMENT_LABEL[e]}
            </button>
          ))}
        </div>
        <div className="card-grid">
          {list.map((c) => (
            <CharCard key={c.id} id={c.id} owned={roster[c.id]} onClick={() => open({ kind: "char", id: c.id })} />
          ))}
        </div>
      </Panel>
    </div>
  );
}
