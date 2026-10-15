// 属性ごとの和柄（背景レイヤー）。<pattern> を返す。
import type { Element } from "../core/types";

export function ElementPattern({ id, element, color }: { id: string; element: Element; color: string }) {
  const stroke = { fill: "none", stroke: color, strokeWidth: 1.2, opacity: 0.55 } as const;
  switch (element) {
    // 炎：鱗文（三角の連続）
    case "fire":
      return (
        <pattern id={id} width="30" height="26" patternUnits="userSpaceOnUse">
          <path d="M0 26 L15 0 L30 26 Z" fill={color} opacity="0.18" />
          <path d="M-15 26 L0 0 L15 26 M15 26 L30 0 L45 26" {...stroke} opacity="0.3" />
        </pattern>
      );
    // 潮：青海波
    case "water":
      return (
        <pattern id={id} width="40" height="20" patternUnits="userSpaceOnUse">
          {[0, 40].map((x) => (
            <g key={x}>
              <circle cx={x} cy="20" r="18" {...stroke} />
              <circle cx={x} cy="20" r="12" {...stroke} />
              <circle cx={x} cy="20" r="6" {...stroke} />
            </g>
          ))}
          <circle cx="20" cy="10" r="18" {...stroke} />
          <circle cx="20" cy="10" r="12" {...stroke} />
          <circle cx="20" cy="10" r="6" {...stroke} />
        </pattern>
      );
    // 嵐：矢絣
    case "wind":
      return (
        <pattern id={id} width="24" height="40" patternUnits="userSpaceOnUse">
          <path d="M0 0 L12 10 L12 30 L0 20 Z" fill={color} opacity="0.2" />
          <path d="M24 0 L12 10 L12 30 L24 20 Z" fill={color} opacity="0.08" />
          <path d="M0 20 L12 30 M24 20 L12 30" {...stroke} opacity="0.35" />
        </pattern>
      );
    // 岩：亀甲
    case "rock":
      return (
        <pattern id={id} width="36" height="62" patternUnits="userSpaceOnUse">
          <path d="M18 2 L34 11 L34 29 L18 38 L2 29 L2 11 Z M18 38 L18 62 M2 29 L-16 40 M34 29 L52 40" {...stroke} />
          <path d="M18 8 L28 14 L28 26 L18 32 L8 26 L8 14 Z" fill={color} opacity="0.12" />
        </pattern>
      );
  }
}
