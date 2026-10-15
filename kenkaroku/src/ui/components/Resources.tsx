import { useGame } from "../../state/store";

export function GemIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden>
      {[0, 72, 144, 216, 288].map((r) => (
        <ellipse key={r} cx="8" cy="4.6" rx="2.6" ry="3.6" fill="#f2a7c4" stroke="#fff3" strokeWidth=".5" transform={`rotate(${r} 8 8)`} />
      ))}
      <circle cx="8" cy="8" r="1.8" fill="var(--k-kin)" />
    </svg>
  );
}

export function GoldIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden>
      <ellipse cx="8" cy="8" rx="7" ry="5.4" fill="var(--k-kin)" stroke="var(--k-kinDeep)" />
      <rect x="6.4" y="6" width="3.2" height="4" fill="var(--k-kinDeep)" />
    </svg>
  );
}

export function ShardIcon({ size = 14, color = "var(--k-shu)" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden>
      <path d="M8 1 C12 4 12 9 8 15 C4 9 4 4 8 1 Z" fill={color} stroke="#fff4" strokeWidth=".6" />
      <path d="M8 3 L8 13" stroke="#fff6" strokeWidth=".6" />
    </svg>
  );
}

export function ResourceBar() {
  const gems = useGame((s) => s.save.gems);
  const gold = useGame((s) => s.save.gold);
  return (
    <div className="k-res">
      <span className="k-res__item">
        <GemIcon /> <span className="num">{gems.toLocaleString()}</span>
      </span>
      <span className="k-res__item">
        <GoldIcon /> <span className="num">{gold.toLocaleString()}</span>
      </span>
    </div>
  );
}
