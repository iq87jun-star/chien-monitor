import { useMemo, useState } from "react";
import { CHAR_BY_ID } from "../../data/characters";
import { availableBanters, teamLeader } from "../../core/dialogue";
import { useGame } from "../../state/store";
import { Panel } from "./Panel";
import { Portrait } from "./Portrait";

/** ホームの掛け合い。編成リーダーと、所持している相手との会話を出す */
export function BanterPanel() {
  const team = useGame((s) => s.save.team);
  const roster = useGame((s) => s.save.roster);
  const leader = teamLeader(team);
  const banters = useMemo(() => availableBanters(leader, Object.keys(roster)), [leader, roster]);
  const [i, setI] = useState(0);
  if (banters.length === 0) return null;
  const b = banters[i % banters.length];
  return (
    <Panel
      title="剣華たちの様子"
      right={
        banters.length > 1 && (
          <button className="k-link" onClick={() => setI(i + 1)}>
            ほかの話
          </button>
        )
      }
    >
      <ul className="banter">
        {b.lines.map((l, k) => {
          const c = CHAR_BY_ID[l.who];
          const left = l.who === b.leader;
          return (
            <li key={k} className={`banter__line ${left ? "is-left" : "is-right"}`} style={{ ["--cc" as string]: c.color, animationDelay: `${k * 0.25}s` }}>
              <span className="banter__face">
                <Portrait id={l.who} crop="face" />
              </span>
              <span className="banter__bubble">
                <b>{c.given}</b>
                {l.text}
              </span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
