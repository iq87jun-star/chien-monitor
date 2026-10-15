import { useState } from "react";
import { CHAR_BY_ID, CHARACTERS } from "../../data/characters";
import { VOICES } from "../../data/voices";
import { useGame } from "../../state/store";
import { charPower, teamPower } from "../hooks";
import { Panel } from "../components/Panel";
import { Sheet } from "../components/Modal";
import { CharCard } from "../components/CharCard";
import { Portrait } from "../components/Portrait";
import { ElementBadge, RoleBadge } from "../components/Badges";
import { Button } from "../components/Button";
import { rarityColor } from "../theme/tokens";

const ROWS = [
  { label: "前列", slots: [0, 1], note: "通常攻撃はまず前列が狙われます" },
  { label: "後列", slots: [2, 3, 4], note: "" },
];

export function Team() {
  const save = useGame((s) => s.save);
  const setSlot = useGame((s) => s.setTeamSlot);
  const setTeam = useGame((s) => s.setTeam);
  const notify = useGame((s) => s.notify);
  const [picking, setPicking] = useState<number | null>(null);

  const autoTeam = () => {
    const ids = Object.keys(save.roster)
      .sort((a, b) => charPower(save, b) - charPower(save, a))
      .slice(0, 5);
    // 守り→攻めの順で前列に置き、術・癒は後列へ
    const frontRank = { def: 0, atk: 1, mag: 2, heal: 3 } as const;
    const sorted = [...ids].sort((a, b) => frontRank[CHAR_BY_ID[a].role] - frontRank[CHAR_BY_ID[b].role]);
    setTeam([sorted[0] ?? null, sorted[1] ?? null, sorted[2] ?? null, sorted[3] ?? null, sorted[4] ?? null]);
  };

  return (
    <div className="screen team">
      <Panel title="編成" right={<span className="k-dim num">戦力 {teamPower(save).toLocaleString()}</span>}>
        {ROWS.map((row) => (
          <div key={row.label} className="team__row">
            <div className="team__row-label brush">{row.label}</div>
            <div className={`team__slots team__slots--${row.slots.length}`}>
              {row.slots.map((slot) => {
                const id = save.team[slot];
                const c = id ? CHAR_BY_ID[id] : null;
                return (
                  <button key={slot} className="team__slot" onClick={() => setPicking(slot)} style={c ? { borderColor: rarityColor(c.rarity) } : undefined}>
                    {c && id ? (
                      <>
                        <Portrait id={id} crop="bust" />
                        <span className="team__slot-name">{c.given}</span>
                        <span className="team__slot-lv num">Lv{save.roster[id]?.level}</span>
                      </>
                    ) : (
                      <span className="team__slot-empty">＋</span>
                    )}
                  </button>
                );
              })}
            </div>
            {row.note && <p className="k-dim team__note">{row.note}</p>}
          </div>
        ))}
        <div className="team__actions">
          <Button variant="ghost" size="sm" onClick={autoTeam}>
            おまかせ編成
          </Button>
        </div>
      </Panel>
      {picking !== null && (
        <Sheet title={`${picking < 2 ? "前列" : "後列"}に置く剣華`} onClose={() => setPicking(null)}>
          <div className="pick-grid">
            {save.team[picking] && (
              <button
                className="pick-remove"
                onClick={() => {
                  setSlot(picking, null);
                  setPicking(null);
                }}
              >
                外す
              </button>
            )}
            {CHARACTERS.filter((c) => save.roster[c.id]).map((c) => {
              const inSlot = save.team.indexOf(c.id);
              return (
                <CharCard
                  key={c.id}
                  id={c.id}
                  owned={save.roster[c.id]}
                  selected={inSlot === picking}
                  note={inSlot >= 0 ? (inSlot < 2 ? "前列" : "後列") : undefined}
                  onClick={() => {
                    setSlot(picking, c.id);
                    setPicking(null);
                    notify(`${c.given}「${VOICES[c.id].formation}」`);
                  }}
                />
              );
            })}
          </div>
        </Sheet>
      )}
      <Panel title="属性と役割">
        <div className="team__legend">
          <p>
            <ElementBadge element="fire" /> → <ElementBadge element="wind" /> → <ElementBadge element="rock" /> → <ElementBadge element="water" /> →{" "}
            <ElementBadge element="fire" />
          </p>
          <p className="k-dim">矢印の先に有利（与ダメージ1.3倍）、逆向きは不利（0.85倍）。</p>
          <p>
            <RoleBadge role="atk" /> 攻：単体火力　<RoleBadge role="mag" /> 術：全体・状態異常　<RoleBadge role="def" /> 守：盾・弱体　
            <RoleBadge role="heal" /> 癒：回復
          </p>
        </div>
      </Panel>
    </div>
  );
}
