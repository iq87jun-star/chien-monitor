import { CHAR_BY_ID } from "../../data/characters";
import { VOICES } from "../../data/voices";
import { bloomStageName, levelCap } from "../../core/economy";
import { BloomFlower } from "../../art/BloomFlower";
import { Portrait } from "./Portrait";
import { Button } from "./Button";

/** 開花演出：花の段階が一段進み、開花台詞を言う */
export function BloomCeremony({ charId, star, onClose }: { charId: string; star: number; onClose: () => void }) {
  const c = CHAR_BY_ID[charId];
  return (
    <div className="bloomc" style={{ ["--cc" as string]: c.color }} onClick={onClose} role="dialog" aria-modal>
      <div className="bloomc__petals" aria-hidden>
        {Array.from({ length: 14 }, (_, i) => (
          <span key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 7) * 0.18}s` }} />
        ))}
      </div>
      <div className="bloomc__box" onClick={(e) => e.stopPropagation()}>
        <div className="bloomc__flower">
          <BloomFlower star={star} color={c.color} size={180} growing />
        </div>
        <div className="bloomc__stage">
          <span className="k-dim">{bloomStageName(star - 1)}</span>
          <span className="bloomc__arrow">→</span>
          <span className="brush bloomc__new">{bloomStageName(star)}</span>
        </div>
        <div className="k-dim num">レベル上限 {levelCap(star - 1)} → {levelCap(star)}</div>
        <div className="bloomc__voice">
          <span className="bloomc__face">
            <Portrait id={charId} crop="face" />
          </span>
          <p>
            <b>{c.given}</b>「{VOICES[charId].bloom}」
          </p>
        </div>
        <Button variant="gold" onClick={onClose} style={{ width: "100%" }}>
          閉じる
        </Button>
      </div>
    </div>
  );
}
