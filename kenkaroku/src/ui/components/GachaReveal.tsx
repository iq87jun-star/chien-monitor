import { useEffect, useState } from "react";
import type { ResolvedPull } from "../../core/gacha";
import type { Rarity } from "../../core/types";
import { CHAR_BY_ID, fullName } from "../../data/characters";
import { VOICES } from "../../data/voices";
import { BloomFlower } from "../../art/BloomFlower";
import { rarityColor } from "../theme/tokens";
import { usePrefersReducedMotion } from "../hooks";
import { Portrait } from "./Portrait";

type Phase = { k: "bud" } | { k: "bloom" } | { k: "ur"; i: number };

const RANK: Record<Rarity, number> = { SR: 0, SSR: 1, UR: 2 };

/**
 * 花結び演出：蕾が開く → 最高レアで花の色が変わる（SR青・SSR紫・UR金）
 * → URは花びらが舞って立ち絵が登場。どこでも「飛ばす」で結果へ。
 */
export function GachaReveal({ results, onDone }: { results: ResolvedPull[]; onDone: () => void }) {
  const reduced = usePrefersReducedMotion();
  const [phase, setPhase] = useState<Phase>({ k: "bud" });
  const top = results.reduce<Rarity>((m, r) => (RANK[r.rarity] > RANK[m] ? r.rarity : m), "SR");
  const urs = results.filter((r) => r.rarity === "UR");

  const next = () => {
    if (phase.k === "bud") setPhase({ k: "bloom" });
    else if (phase.k === "bloom") urs.length ? setPhase({ k: "ur", i: 0 }) : onDone();
    else if (phase.i + 1 < urs.length) setPhase({ k: "ur", i: phase.i + 1 });
    else onDone();
  };

  // 蕾と開花は自動で進む（URの登場はタップ待ち）
  useEffect(() => {
    if (phase.k === "ur") return;
    const t = setTimeout(next, phase.k === "bud" ? (reduced ? 300 : 1300) : reduced ? 500 : 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const color = rarityColor(top);
  return (
    <div className={`gr gr--${top} ${reduced ? "is-reduced" : ""}`} style={{ ["--gc" as string]: color }} onClick={next} role="dialog" aria-modal aria-label="花結び">
      <button
        className="k-chip gr__skip"
        onClick={(e) => {
          e.stopPropagation();
          onDone();
        }}
      >
        飛ばす
      </button>

      {phase.k !== "ur" && (
        <div className={`gr__flower gr__flower--${phase.k}`}>
          {phase.k === "bud" ? <BloomFlower star={1} color="#e9dcc4" size={200} /> : <BloomFlower star={10} color={color} size={260} />}
          {phase.k === "bloom" && <div className="gr__burst" />}
        </div>
      )}
      {phase.k === "bud" && <p className="gr__hint brush">花が、結ばれる……</p>}
      {phase.k === "bloom" && <p className="gr__hint brush gr__rarity">{top === "UR" ? "金の花が咲いた！" : top === "SSR" ? "紫の花が咲いた" : "青い花が咲いた"}</p>}

      {phase.k === "ur" && <UrEntrance pull={urs[phase.i]} reduced={reduced} />}
      {(phase.k === "ur" || (phase.k === "bloom" && top === "UR")) && !reduced && (
        <div className="gr__petals" aria-hidden>
          {Array.from({ length: 24 }, (_, i) => (
            <span key={i} style={{ left: `${(i * 41) % 100}%`, animationDelay: `${(i % 8) * 0.2}s` }} />
          ))}
        </div>
      )}
    </div>
  );
}

function UrEntrance({ pull, reduced }: { pull: ResolvedPull; reduced: boolean }) {
  const c = CHAR_BY_ID[pull.charId];
  return (
    <div className={`gr__ur ${reduced ? "" : "is-anim"}`} style={{ ["--cc" as string]: c.color }} key={pull.charId}>
      <div className="gr__ur-art">
        <Portrait id={pull.charId} crop="full" />
      </div>
      <div className="gr__ur-text">
        <div className="gr__ur-epithet">{c.epithet}</div>
        <div className="gr__ur-name brush">{fullName(c)}</div>
        <p className="gr__ur-line">「{VOICES[c.id].formation}」</p>
        <div className="k-dim">{pull.isNew ? "新たな剣華が加わった" : "花片 +10"}・タップで次へ</div>
      </div>
    </div>
  );
}
