// 開花の段階を表す花。★1=蕾、★10=満開（10枚の花びら）。
export function BloomFlower({
  star,
  color,
  size = 96,
  growing = false,
}: {
  star: number;
  color: string;
  size?: number;
  /** 最後の1枚を伸びるアニメーションにする */
  growing?: boolean;
}) {
  const petals = Math.max(0, Math.min(10, star));
  return (
    <svg width={size} height={size} viewBox="-50 -50 100 100" aria-hidden className="bloom-flower">
      {/* 空きの花びら（輪郭だけ） */}
      {Array.from({ length: 10 }, (_, i) => (
        <path
          key={`o${i}`}
          d="M0 -6 C8 -16 8 -32 0 -44 C-8 -32 -8 -16 0 -6 Z"
          transform={`rotate(${i * 36})`}
          fill="none"
          stroke="rgba(243,234,216,.18)"
          strokeWidth="1"
        />
      ))}
      {petals <= 1 ? (
        // 蕾
        <g className={growing ? "bloom-flower__grow" : undefined}>
          <path d="M0 18 C-14 6 -12 -16 0 -30 C12 -16 14 6 0 18 Z" fill={color} />
          <path d="M0 18 C-6 6 -6 -12 0 -26" stroke="rgba(255,255,255,.4)" strokeWidth="1.2" fill="none" />
          <path d="M0 18 C-10 18 -16 10 -18 2 C-8 4 -4 10 0 18 Z M0 18 C10 18 16 10 18 2 C8 4 4 10 0 18 Z" fill="#4f7a3e" />
        </g>
      ) : (
        Array.from({ length: petals }, (_, i) => (
          <path
            key={i}
            className={growing && i === petals - 1 ? "bloom-flower__grow" : undefined}
            d="M0 -6 C8 -16 8 -32 0 -44 C-8 -32 -8 -16 0 -6 Z"
            transform={`rotate(${i * 36})`}
            fill={color}
            stroke="rgba(255,255,255,.35)"
            strokeWidth=".8"
            style={{ transformOrigin: "0 0" }}
          />
        ))
      )}
      {petals > 1 && <circle r="7" fill="#e8c45a" stroke="#8f6f2c" />}
    </svg>
  );
}
