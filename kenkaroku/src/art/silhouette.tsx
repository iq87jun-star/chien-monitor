// 立ち絵のシルエット（髪型・体・武器）。300×400 の座標系。
// 頭の中心は (150,140)。シルエットは墨色で塗り、テーマカラーで縁取ってキャラを見分けやすくする。
import type { ReactNode } from "react";
import type { HairStyle, WeaponShape } from "../data/characters";

export interface Layer {
  back?: ReactNode;
  front?: ReactNode;
}

const STEEL = "#d9dee2";
const WOOD = "#7a5530";

// 前髪（流し）
const BANGS_SWEPT = "M112 150 C108 104 128 88 150 88 C176 88 194 106 188 150 C180 130 170 120 158 118 L150 134 L140 118 C128 122 118 134 112 150 Z";
// 前髪（ぱっつん）
const BANGS_STRAIGHT = "M112 150 C108 104 128 90 150 90 C172 90 192 104 188 150 L184 128 L116 128 Z";
// 後頭部
const BACK_HEAD = <ellipse cx="150" cy="132" rx="42" ry="44" />;

export function hair(style: HairStyle, accent: string): Layer {
  switch (style) {
    case "longSide":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M114 120 C92 170 98 260 84 336 C106 326 116 300 120 262 C124 222 132 190 140 168 Z" />
            <path d="M186 120 C198 150 200 180 192 200 C188 180 184 160 176 150 Z" />
            {/* 赤い組紐 */}
            <path d="M112 150 l-10 8 l6 4 l-8 14" fill="none" stroke={accent} strokeWidth="3" />
          </>
        ),
        front: <path d={BANGS_SWEPT} />,
      };
    case "hime":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M112 120 L104 330 L132 330 L136 170 Z" />
            <path d="M188 120 L196 330 L168 330 L164 170 Z" />
          </>
        ),
        front: (
          <>
            <path d={BANGS_STRAIGHT} />
            <path d="M114 126 L112 192 L124 192 L124 130 Z" />
            <path d="M186 126 L188 192 L176 192 L176 130 Z" />
          </>
        ),
      };
    case "hoodShort":
      return {
        back: <path d="M100 176 C96 112 118 78 150 70 C182 78 204 112 200 176 Z" />,
        front: (
          <>
            <path d="M100 176 C96 112 118 78 150 70 C182 78 204 112 200 176 C194 150 188 128 172 118 L128 118 C112 128 106 150 100 176 Z" />
            <path d="M150 70 L162 52 L158 74 Z" />
            <path d="M126 120 L134 132 L142 120 L150 134 L158 120 L166 132 L174 120 Z" />
            {/* 片目のレンズ */}
            <circle cx="164" cy="146" r="8" fill="none" stroke={accent} strokeWidth="2.5" />
            <circle cx="164" cy="146" r="4" fill={accent} opacity=".6" />
          </>
        ),
      };
    case "wildLong":
      return {
        back: (
          <path d="M150 80 L170 70 L178 86 L200 82 L198 104 L220 110 L206 130 L226 150 L206 162 L222 190 L200 192 L212 230 L190 222 L196 270 L176 246 L168 290 L150 250 L132 290 L124 246 L104 270 L110 222 L88 230 L100 192 L78 190 L94 162 L74 150 L94 130 L80 110 L102 104 L100 82 L122 86 L130 70 Z" />
        ),
        front: <path d="M112 150 C108 106 124 90 150 90 C176 90 192 106 188 150 L178 126 L170 136 L162 120 L150 134 L140 118 L130 136 L122 126 Z" />,
      };
    case "bunBells":
      return {
        back: (
          <>
            {BACK_HEAD}
            <circle cx="120" cy="96" r="18" />
            <circle cx="180" cy="96" r="18" />
            <path d="M110 140 C104 180 108 210 116 230 L124 230 C120 200 120 170 122 150 Z" />
            <path d="M190 140 C196 180 192 210 184 230 L176 230 C180 200 180 170 178 150 Z" />
          </>
        ),
        front: (
          <>
            <path d={BANGS_SWEPT} />
            {/* 雨粒の簪 */}
            {[
              [104, 92],
              [196, 92],
            ].map(([x, y]) => (
              <g key={x}>
                <path d={`M${x} ${y} L${x} ${y + 26}`} stroke={accent} strokeWidth="1.5" />
                <path d={`M${x} ${y + 26} c-4 6 -4 10 0 12 c4 -2 4 -6 0 -12 Z`} fill={accent} />
              </g>
            ))}
          </>
        ),
      };
    case "short":
      return {
        back: <ellipse cx="150" cy="128" rx="44" ry="42" />,
        front: <path d="M108 150 L104 120 L116 124 L114 100 L130 106 L134 84 L150 98 L162 80 L170 100 L188 90 L186 112 L200 112 L190 132 L194 150 L180 130 L168 136 L160 118 L150 132 L140 118 L130 136 L118 128 Z" />,
      };
    case "scarfLow":
      return {
        back: (
          <>
            <ellipse cx="150" cy="128" rx="40" ry="40" />
            <path d="M186 170 C232 176 254 214 278 270 C246 238 224 218 190 196 Z" />
            <path d="M190 182 C236 200 250 250 262 300 C238 260 220 236 188 210 Z" />
          </>
        ),
        front: (
          <>
            <path d="M112 146 C108 104 128 92 150 92 C172 92 192 104 188 146 L180 124 L170 132 L164 116 L150 128 L136 116 L130 132 L120 124 Z" />
            <path d="M108 150 Q150 178 192 150 L196 188 Q150 206 104 188 Z" />
          </>
        ),
      };
    case "ponytail":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M178 104 C232 116 240 200 216 276 C214 226 200 162 172 128 Z" />
            <circle cx="182" cy="106" r="6" fill={accent} stroke="none" />
          </>
        ),
        front: <path d={BANGS_SWEPT} />,
      };
    case "sideTail":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M120 110 C78 130 74 214 90 274 C94 222 104 160 128 132 Z" />
            <circle cx="118" cy="112" r="6" fill={accent} stroke="none" />
          </>
        ),
        front: <path d={BANGS_SWEPT} />,
      };
    case "twinTail":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M116 104 C78 120 72 200 84 262 C90 210 100 160 124 128 Z" />
            <path d="M184 104 C222 120 228 200 216 262 C210 210 200 160 176 128 Z" />
            <circle cx="114" cy="106" r="6" fill={accent} stroke="none" />
            <circle cx="186" cy="106" r="6" fill={accent} stroke="none" />
          </>
        ),
        front: <path d={BANGS_SWEPT} />,
      };
    case "bob":
      return {
        back: <path d="M108 120 C100 160 106 184 116 192 L184 192 C194 184 200 160 192 120 C186 96 168 86 150 86 C132 86 114 96 108 120 Z" />,
        front: <path d="M112 150 C108 104 128 90 150 90 C172 90 192 104 188 150 L180 126 L164 132 L150 122 L136 132 L120 126 Z" />,
      };
    case "highTail":
      return {
        back: (
          <>
            {BACK_HEAD}
            <path d="M146 92 C150 48 200 36 238 66 C210 60 190 70 170 100 Z" />
            <path d="M200 58 C242 88 250 160 228 214 C230 164 216 112 180 96 Z" />
            <circle cx="152" cy="90" r="6" fill={accent} stroke="none" />
          </>
        ),
        front: <path d={BANGS_SWEPT} />,
      };
    case "fluffy":
      return {
        back: (
          <>
            <circle cx="150" cy="132" r="50" />
            <circle cx="104" cy="160" r="22" />
            <circle cx="196" cy="160" r="22" />
            <circle cx="110" cy="196" r="18" />
            <circle cx="190" cy="196" r="18" />
          </>
        ),
        front: (
          <>
            <path d="M110 150 C104 104 126 86 150 86 C176 86 196 104 190 150 C186 132 176 118 164 116 C160 124 150 128 142 120 C130 122 116 132 110 150 Z" />
            {/* 柚子の髪飾り */}
            <circle cx="122" cy="98" r="8" fill={accent} stroke="none" />
          </>
        ),
      };
    case "hairpinBob":
      return {
        back: <path d="M108 120 C100 160 106 184 116 192 L184 192 C194 184 200 160 192 120 C186 96 168 86 150 86 C132 86 114 96 108 120 Z" />,
        front: (
          <>
            <path d={BANGS_STRAIGHT} />
            {/* 頭の横に狐面 */}
            <g transform="translate(176 84) rotate(18) scale(.36)" fill="#f6efe0" stroke="none">
              <path d="M18 14 L36 34 L64 34 L82 14 L80 48 C78 72 64 90 50 92 C36 90 22 72 20 48 Z" />
              <path d="M30 50 L44 56 M70 50 L56 56" stroke="#c8283c" strokeWidth="5" />
            </g>
          </>
        ),
      };
  }
}

const blade = (d: string, w = 5) => <path d={d} fill="none" stroke={STEEL} strokeWidth={w} strokeLinecap="round" />;

export function weapon(shape: WeaponShape, color: string, sub: string): Layer {
  switch (shape) {
    case "twinKatana":
      return {
        back: (
          <g>
            {blade("M84 68 Q140 180 214 306", 5)}
            {blade("M222 72 Q166 186 92 300", 5)}
            <path d="M84 68 L64 30" stroke={color} strokeWidth="9" strokeLinecap="round" />
            <path d="M222 72 L240 34" stroke={color} strokeWidth="9" strokeLinecap="round" />
            <path d="M74 56 L94 48 M212 60 L232 52" stroke="#e8c45a" strokeWidth="4" />
          </g>
        ),
      };
    case "naginata":
      return {
        back: (
          <g>
            <path d="M56 390 L238 70" stroke={WOOD} strokeWidth="7" strokeLinecap="round" />
            <path d="M232 80 C246 50 262 30 286 14 C276 44 262 70 244 90 Z" fill={STEEL} />
            <path d="M226 92 L250 104" stroke={sub} strokeWidth="5" />
          </g>
        ),
      };
    case "caneSword":
      return {
        back: (
          <g>
            {blade("M236 70 L236 330", 4)}
            <rect x="228" y="300" width="16" height="70" rx="4" fill="#2b2b33" stroke={sub} strokeWidth="2" />
            <circle cx="236" cy="300" r="12" fill="none" stroke={sub} strokeWidth="4" strokeDasharray="5 3" />
            {/* 鴉の羽 */}
            <path d="M60 220 C40 200 34 170 44 150 C52 176 66 192 80 204 Z" fill="#1a1a22" stroke={color} strokeWidth="1.5" />
            <path d="M56 250 C30 236 22 210 28 190 C40 214 58 226 74 234 Z" fill="#1a1a22" stroke={color} strokeWidth="1.5" />
          </g>
        ),
      };
    case "towerShield":
      return {
        front: (
          <g>
            <rect x="34" y="214" width="112" height="176" rx="8" fill="#3a3436" stroke={sub} strokeWidth="3" />
            {[236, 300, 364].map((y) => (
              <path key={y} d={`M34 ${y} L146 ${y}`} stroke="#57504c" strokeWidth="3" />
            ))}
            {[
              [46, 226],
              [134, 226],
              [46, 378],
              [134, 378],
            ].map(([x, y]) => (
              <circle key={`${x}${y}`} cx={x} cy={y} r="4" fill={sub} />
            ))}
            {/* 注連縄 */}
            <path d="M28 214 Q90 236 152 214" fill="none" stroke="#e8dcb0" strokeWidth="7" strokeDasharray="10 4" />
            <path d="M70 226 l0 18 l-6 0 M110 226 l0 18 l6 0" stroke="#f3ead8" strokeWidth="3" fill="none" />
          </g>
        ),
      };
    case "kaguraBell":
      return {
        front: (
          <g>
            <path d="M214 296 L226 196" stroke="#c8283c" strokeWidth="6" strokeLinecap="round" />
            {[
              [226, 178],
              [214, 188],
              [238, 190],
              [220, 166],
              [234, 166],
              [226, 152],
            ].map(([x, y]) => (
              <circle key={`${x}${y}`} cx={x} cy={y} r="7" fill="#e8c45a" stroke="#8f6f2c" strokeWidth="1.5" />
            ))}
            <path d="M214 296 C200 330 206 360 196 390" stroke={color} strokeWidth="4" fill="none" />
            <path d="M216 296 C226 330 236 350 232 390" stroke={sub} strokeWidth="4" fill="none" />
          </g>
        ),
      };
    case "odachi":
      return {
        back: (
          <g>
            <path d="M58 360 Q170 200 286 18" fill="none" stroke={STEEL} strokeWidth="10" strokeLinecap="round" />
            <path d="M58 360 L28 404" stroke={color} strokeWidth="12" strokeLinecap="round" />
            <path d="M48 344 L74 368" stroke="#e8c45a" strokeWidth="6" />
          </g>
        ),
      };
    case "kunai":
      return {
        front: (
          <g>
            {[
              [236, 200, 30],
              [258, 240, 45],
              [232, 276, 20],
            ].map(([x, y, r]) => (
              <g key={`${x}${y}`} transform={`translate(${x} ${y}) rotate(${r})`}>
                <path d="M0 -26 L6 -4 L0 0 L-6 -4 Z" fill={STEEL} />
                <path d="M0 0 L0 14" stroke="#1a1a22" strokeWidth="3" />
                <circle cx="0" cy="18" r="4" fill="none" stroke={sub} strokeWidth="2" />
              </g>
            ))}
          </g>
        ),
      };
    case "twinShields":
      return {
        front: (
          <g fill="#eae4d4" stroke={color} strokeWidth="2.5">
            <path d="M104 236 C70 214 40 206 18 214 C30 240 34 280 30 316 C60 300 86 296 108 300 Z" />
            <path d="M196 236 C230 214 260 206 282 214 C270 240 266 280 270 316 C240 300 214 296 192 300 Z" />
            <path d="M40 236 L96 262 M44 268 L98 280 M260 236 L204 262 M256 268 L202 280" stroke={color} strokeWidth="1.5" />
          </g>
        ),
      };
    case "crossSpear":
      return {
        back: (
          <g>
            <path d="M246 396 L246 54" stroke={WOOD} strokeWidth="6" />
            <path d="M246 10 L254 54 L238 54 Z" fill={STEEL} />
            <path d="M212 60 L280 60" stroke={STEEL} strokeWidth="6" strokeLinecap="round" />
            <path d="M212 60 L206 48 M280 60 L286 48" stroke={STEEL} strokeWidth="5" strokeLinecap="round" />
            <path d="M240 72 L252 72" stroke={sub} strokeWidth="6" />
          </g>
        ),
      };
    case "bow":
      return {
        back: (
          <g>
            <path d="M74 20 C20 140 20 260 74 384" fill="none" stroke={WOOD} strokeWidth="7" strokeLinecap="round" />
            <path d="M74 20 L74 384" stroke="#e8dcb0" strokeWidth="1.5" />
            <path d="M70 196 L78 196" stroke={color} strokeWidth="10" />
            {/* 雲雀の羽根の矢 */}
            <path d="M232 120 L232 300" stroke={WOOD} strokeWidth="3" />
            <path d="M232 112 l-5 12 l10 0 Z" fill={color} />
            <path d="M232 290 l-8 14 M232 290 l8 14" stroke={sub} strokeWidth="3" />
          </g>
        ),
      };
    case "bokken":
      return {
        front: (
          <g>
            <path d="M196 340 L272 70" stroke="#b08a58" strokeWidth="9" strokeLinecap="round" />
            <path d="M186 312 L208 320" stroke="#3a2a1a" strokeWidth="6" />
          </g>
        ),
      };
    case "pinwheel":
      return {
        front: (
          <g>
            <path d="M244 360 L244 236" stroke={WOOD} strokeWidth="4" />
            <g transform="translate(244 230)">
              {[0, 90, 180, 270].map((r, i) => (
                <path key={r} d="M0 0 L0 -34 L22 -18 Z" fill={i % 2 ? sub : color} stroke="#0006" transform={`rotate(${r})`} />
              ))}
              <circle r="4" fill="#e8c45a" />
            </g>
          </g>
        ),
      };
    case "staff":
      return {
        back: (
          <g>
            <path d="M54 392 L250 40" stroke={WOOD} strokeWidth="8" strokeLinecap="round" />
            <path d="M244 50 L256 30 M60 380 L48 400" stroke="#9a9aa2" strokeWidth="10" />
          </g>
        ),
      };
    case "lantern":
      return {
        front: (
          <g>
            <path d="M206 330 L246 150 L262 150" stroke={WOOD} strokeWidth="4" fill="none" />
            <path d="M262 150 L262 168" stroke="#2a2a2a" strokeWidth="2" />
            <ellipse cx="262" cy="200" rx="22" ry="32" fill="#ffb054" />
            <ellipse cx="262" cy="200" rx="22" ry="32" fill="none" stroke="#c8283c" strokeWidth="2" />
            {[184, 196, 208, 220].map((y) => (
              <path key={y} d={`M242 ${y} Q262 ${y + 4} 282 ${y}`} stroke="#c06a2a" strokeWidth="1" fill="none" />
            ))}
            <rect x="250" y="166" width="24" height="5" fill="#2a2a2a" />
            <rect x="250" y="229" width="24" height="5" fill="#2a2a2a" />
          </g>
        ),
      };
  }
}

/** 着物の胴体（共通） */
export function Body({ color, sub }: { color: string; sub: string }) {
  return (
    <g>
      <rect x="138" y="166" width="24" height="34" />
      <path d="M62 404 L76 262 Q86 208 150 196 Q214 208 224 262 L238 404 Z" />
      {/* 袖 */}
      <path d="M80 236 L30 372 L98 388 L104 290 Z" />
      <path d="M220 236 L270 372 L202 388 L196 290 Z" />
      <path d="M30 372 L98 388" stroke={color} strokeWidth="4" />
      <path d="M270 372 L202 388" stroke={color} strokeWidth="4" />
      {/* 衿 */}
      <path d="M128 200 L150 262 L172 200" fill="none" stroke={sub} strokeWidth="6" strokeLinejoin="round" />
      {/* 帯 */}
      <path d="M86 300 Q150 314 214 300 L216 330 Q150 344 84 330 Z" fill={color} stroke="none" />
      <path d="M90 316 Q150 330 210 316" stroke={sub} strokeWidth="2" fill="none" />
    </g>
  );
}
