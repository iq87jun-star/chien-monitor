import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "gold";

export function Button({
  variant = "primary",
  size = "md",
  children,
  className = "",
  ...rest
}: { variant?: Variant; size?: "sm" | "md" | "lg"; children: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`k-btn k-btn--${variant} k-btn--${size} ${className}`} {...rest}>
      <span className="k-btn__label">{children}</span>
    </button>
  );
}
