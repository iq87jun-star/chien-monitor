export function Bar({
  value,
  max,
  color,
  height = 6,
  extra,
  extraColor,
}: {
  value: number;
  max: number;
  color: string;
  height?: number;
  /** 盾など、本体の上に重ねる量 */
  extra?: number;
  extraColor?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const ex = extra && max > 0 ? Math.min(100, (extra / max) * 100) : 0;
  return (
    <div className="k-bar" style={{ height }}>
      <div className="k-bar__fill" style={{ width: `${pct}%`, background: color }} />
      {ex > 0 && <div className="k-bar__extra" style={{ width: `${ex}%`, background: extraColor }} />}
    </div>
  );
}
