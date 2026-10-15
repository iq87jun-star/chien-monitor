import type { CSSProperties, ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
  style,
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <section className={`k-panel kintsugi ${className}`} style={style}>
      {(title || right) && (
        <header className="k-panel__head">
          {title && <h2 className="k-panel__title brush">{title}</h2>}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Divider() {
  return <div className="k-divider" role="presentation" />;
}
