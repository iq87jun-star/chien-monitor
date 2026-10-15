import { CHAR_BY_ID } from "../../data/characters";
import { VOICES } from "../../data/voices";
import { Portrait } from "./Portrait";

/** スキル発動時のカットイン。テーマカラーの帯が斜めに走り、二つ名・技名・台詞を出す */
export function Cutin({ charId, durationMs, reduced }: { charId: string; durationMs: number; reduced: boolean }) {
  const c = CHAR_BY_ID[charId];
  if (!c) return null;
  return (
    <div
      className={`cutin ${reduced ? "is-reduced" : ""}`}
      style={{ ["--cc" as string]: c.color, ["--cs" as string]: c.colorSub, ["--dur" as string]: `${durationMs}ms` }}
      aria-live="polite"
    >
      <div className="cutin__band">
        <div className="cutin__art">
          <Portrait id={charId} crop="bust" frame={false} />
        </div>
        <div className="cutin__text">
          <div className="cutin__epithet">{c.epithet}</div>
          <div className="cutin__skill brush">{c.skill.name}</div>
          <div className="cutin__line">「{VOICES[charId]?.skill}」</div>
        </div>
      </div>
    </div>
  );
}

/** 速度に応じたカットイン時間（×1で0.8秒、×2以上で短縮） */
export function cutinDuration(speed: number): number {
  return speed >= 4 ? 320 : speed >= 2 ? 480 : 800;
}
