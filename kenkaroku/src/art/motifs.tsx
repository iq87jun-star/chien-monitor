// キャラ固有のモチーフ紋。100×100 の座標系で描き、呼び出し側で拡大・配置する。
import type { MotifKey } from "../data/characters";

const petal = (rot: number, fill: string) => (
  <path key={rot} d="M50 50 C38 36 40 18 50 12 L53 18 L56 12 C64 20 62 36 50 50 Z" fill={fill} transform={`rotate(${rot} 50 50)`} />
);

export function Motif({ motif, color, accent }: { motif: MotifKey; color: string; accent: string }) {
  switch (motif) {
    case "sakura":
      return (
        <g>
          {[0, 72, 144, 216, 288].map((r) => petal(r, color))}
          <circle cx="50" cy="50" r="6" fill={accent} />
        </g>
      );
    case "snow":
      return (
        <g stroke={color} strokeWidth="4" strokeLinecap="round" fill="none">
          {[0, 60, 120].map((r) => (
            <g key={r} transform={`rotate(${r} 50 50)`}>
              <path d="M50 10 L50 90" />
              <path d="M50 22 L42 14 M50 22 L58 14 M50 78 L42 86 M50 78 L58 86" />
              <path d="M50 34 L40 28 M50 34 L60 28 M50 66 L40 72 M50 66 L60 72" />
            </g>
          ))}
        </g>
      );
    case "gear":
      return (
        <g>
          {Array.from({ length: 10 }, (_, i) => (
            <rect key={i} x="45" y="8" width="10" height="16" rx="2" fill={color} transform={`rotate(${i * 36} 50 50)`} />
          ))}
          <circle cx="50" cy="50" r="30" fill={color} />
          <circle cx="50" cy="50" r="12" fill={accent} />
          <path d="M70 70 C80 76 92 72 96 62 C88 66 80 64 74 58 Z" fill={accent} opacity=".9" />
        </g>
      );
    case "onigawara":
      return (
        <g>
          <path d="M10 80 C10 40 30 16 50 16 C70 16 90 40 90 80 Z" fill={color} />
          <path d="M28 22 L20 4 L36 18 M72 22 L80 4 L64 18" fill={color} stroke={color} strokeWidth="3" />
          <path d="M30 46 L44 52 M70 46 L56 52" stroke={accent} strokeWidth="5" strokeLinecap="round" />
          <path d="M32 66 Q50 58 68 66 L64 74 L56 68 L50 74 L44 68 L36 74 Z" fill={accent} />
          <path d="M6 88 L94 88" stroke={accent} strokeWidth="5" strokeDasharray="10 6" />
        </g>
      );
    case "lotus":
      return (
        <g>
          <path d="M50 20 C60 34 60 56 50 70 C40 56 40 34 50 20 Z" fill={color} />
          <path d="M50 70 C40 50 22 42 14 46 C18 60 34 70 50 70 Z" fill={color} opacity=".85" />
          <path d="M50 70 C60 50 78 42 86 46 C82 60 66 70 50 70 Z" fill={color} opacity=".85" />
          <path d="M50 70 C34 66 12 66 6 72 C20 80 40 78 50 70 Z M50 70 C66 66 88 66 94 72 C80 80 60 78 50 70 Z" fill={color} opacity=".65" />
          <path d="M30 86 Q50 80 70 86" stroke={accent} strokeWidth="3" fill="none" />
          <circle cx="78" cy="22" r="4" fill={accent} />
          <circle cx="86" cy="34" r="3" fill={accent} />
        </g>
      );
    case "flameScale":
      return (
        <g>
          <path d="M50 6 C60 26 80 34 76 60 C74 80 60 92 50 92 C40 92 26 80 24 60 C22 42 36 36 40 20 C44 32 46 36 50 38 C50 26 48 16 50 6 Z" fill={color} />
          <path d="M50 46 C56 56 64 62 62 74 C60 84 54 88 50 88 C46 88 40 84 38 74 C38 64 46 58 50 46 Z" fill={accent} />
        </g>
      );
    case "newMoon":
      return (
        <g>
          <circle cx="50" cy="50" r="38" fill="none" stroke={color} strokeWidth="3" opacity=".7" />
          <path d="M56 14 A36 36 0 1 0 56 86 A28 28 0 1 1 56 14 Z" fill={color} />
          <path d="M70 30 L82 18 M76 44 L92 40" stroke={accent} strokeWidth="3" strokeLinecap="round" />
        </g>
      );
    case "crane":
      return (
        <g>
          <path d="M10 56 L50 46 L36 18 Z" fill={color} />
          <path d="M90 56 L50 46 L64 18 Z" fill={color} opacity=".8" />
          <path d="M50 46 L36 70 L64 70 Z" fill={color} />
          <path d="M36 70 L14 64 L22 58 Z" fill={color} />
          <path d="M64 70 L86 54 L80 50 L72 60 Z" fill={color} />
          <circle cx="83" cy="52" r="3" fill={accent} />
        </g>
      );
    case "maple":
      return (
        <g>
          <path
            d="M50 6 L57 28 L72 18 L68 38 L90 34 L76 50 L92 60 L70 62 L74 80 L56 68 L50 94 L44 68 L26 80 L30 62 L8 60 L24 50 L10 34 L32 38 L28 18 L43 28 Z"
            fill={color}
          />
          <path d="M50 30 L50 96" stroke={accent} strokeWidth="2" />
          <path d="M8 84 Q30 76 50 86 T92 84" stroke={accent} strokeWidth="3" fill="none" />
        </g>
      );
    case "bonfire":
      return (
        <g>
          <path d="M50 8 C62 28 74 34 70 56 C68 70 60 76 50 76 C40 76 32 70 30 56 C28 40 42 34 44 18 C48 28 50 30 50 8 Z" fill={color} />
          <path d="M22 92 L78 70 M78 92 L22 70" stroke={accent} strokeWidth="7" strokeLinecap="round" />
          <path d="M80 22 L92 16 L86 28 Z" fill={accent} />
        </g>
      );
    case "snowRabbit":
      return (
        <g>
          <ellipse cx="50" cy="64" rx="34" ry="22" fill={color} />
          <path d="M36 46 C30 26 34 14 40 16 C44 26 42 38 42 46 Z M56 46 C56 30 60 18 66 18 C70 26 64 38 62 46 Z" fill="#6caa5c" />
          <circle cx="40" cy="60" r="3.5" fill={accent} />
          <circle cx="58" cy="60" r="3.5" fill={accent} />
        </g>
      );
    case "aoi":
      return (
        <g>
          <circle cx="50" cy="50" r="44" fill="none" stroke={color} strokeWidth="4" />
          {[0, 120, 240].map((r) => (
            <g key={r} transform={`rotate(${r} 50 50)`}>
              <path d="M50 50 C36 40 34 22 42 16 C46 14 50 18 50 22 C50 18 54 14 58 16 C66 22 64 40 50 50 Z" fill={color} />
              <path d="M50 48 L50 24" stroke={accent} strokeWidth="1.5" />
            </g>
          ))}
        </g>
      );
    case "yuzu":
      return (
        <g>
          <circle cx="48" cy="56" r="34" fill={color} />
          <circle cx="38" cy="46" r="6" fill="#fff" opacity=".35" />
          <path d="M50 24 C56 10 72 6 84 12 C76 24 62 28 50 24 Z" fill="#5c9a4a" />
          <path d="M20 90 L30 80 L40 90 L50 80 L60 90 L70 80 L80 90" stroke={accent} strokeWidth="3" fill="none" />
        </g>
      );
    case "foxMask":
      return (
        <g>
          <path d="M18 14 L36 34 L64 34 L82 14 L80 48 C78 72 64 90 50 92 C36 90 22 72 20 48 Z" fill={color} />
          <path d="M30 50 L44 56 M70 50 L56 56" stroke="#c8283c" strokeWidth="4" strokeLinecap="round" />
          <path d="M24 26 L32 36 M76 26 L68 36" stroke="#c8283c" strokeWidth="3" />
          <path d="M44 76 L50 80 L56 76" stroke={accent} strokeWidth="3" fill="none" />
        </g>
      );
  }
}
