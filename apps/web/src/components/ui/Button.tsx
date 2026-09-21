import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/helpers/cn";

type Variant = "primary" | "accent" | "secondary" | "text" | "danger";
type Size = "sm" | "md" | "lg";

/**
 * Cada variante trae su propio estado deshabilitado en vez de una opacidad
 * generica: sobre el acento amarillo, bajar la opacidad da un tono que no
 * cumple contraste con el texto gris tinta.
 */
const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-surface hover:bg-brand-hover disabled:bg-line disabled:text-disabled",
  accent:
    "bg-accent text-ink hover:bg-accent-hover disabled:bg-accent-disabled disabled:text-accent-on-disabled",
  secondary:
    "border-[1.5px] border-line-strong bg-surface text-ink hover:border-brand hover:text-brand " +
    "disabled:border-line disabled:text-disabled-soft",
  text: "text-brand underline underline-offset-4 hover:text-brand-hover disabled:text-disabled-soft",
  danger: "bg-danger text-surface hover:brightness-90 disabled:bg-line disabled:text-disabled",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-[40px] px-[18px] py-[9px] text-[14px] leading-[22px] rounded-lg",
  md: "min-h-[48px] px-[26px] py-3 text-[16px] leading-6 rounded-control",
  lg: "min-h-[56px] px-8 py-[15px] text-[17px] leading-[26px] rounded-control",
};

/** El secundario descuenta su borde de 1.5px para no crecer sobre la altura. */
const SECONDARY_SIZES: Record<Size, string> = {
  sm: "py-[7.5px]",
  md: "py-[10.5px]",
  lg: "py-[13.5px]",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
  children: ReactNode;
}

/** Boton de presentacion pura: no conoce ni el dominio ni el estado global. */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  className,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      // Un boton en curso se deshabilita para que no se pueda enviar dos veces.
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold",
        "transition-colors focus-visible:outline-none focus-visible:ring-2",
        "focus-visible:ring-brand focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed",
        variant === "text" && "min-h-0 rounded-none px-0 py-0",
        variant !== "text" && SIZES[size],
        variant === "secondary" && SECONDARY_SIZES[size],
        VARIANTS[variant],
        fullWidth && "w-full",
        className,
      )}
    >
      {loading && (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}
