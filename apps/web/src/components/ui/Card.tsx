import type { ReactNode } from "react";

import { cn } from "@/helpers/cn";

/**
 * Superficie blanca sobre el fondo de pagina.
 *
 * Plana por definicion: la elevacion del sistema se reserva a menus y modales,
 * asi que una tarjeta de listado nunca lleva sombra.
 */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-card border border-line bg-surface p-6", className)}>
      {children}
    </div>
  );
}

/** Panel: la superficie grande (formulario, tablero), con radio mayor. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-panel border border-line bg-surface p-6", className)}>
      {children}
    </div>
  );
}

type TagTone = "trade" | "trade-dark" | "neutral" | "accent";

const TAG_TONES: Record<TagTone, string> = {
  trade: "bg-brand-soft text-brand px-[11px] py-1.5 text-xs tracking-[0.7px] rounded-tag",
  // Sobre fondo oscuro el gremio se pinta en amarillo con texto gris tinta:
  // blanco sobre amarillo no cumple AA.
  "trade-dark": "bg-accent text-ink px-2.5 py-[5px] text-[11.5px] font-bold rounded-[5px]",
  neutral: "bg-page text-muted px-[11px] py-1.5 text-xs tracking-[0.7px] rounded-tag",
  accent: "bg-accent-disabled text-ink px-[11px] py-1.5 text-xs tracking-[0.7px] rounded-tag",
};

/** Etiqueta de gremio o de estado. Mayusculas y peso 600 por sistema. */
export function Tag({
  children,
  tone = "trade",
  className,
}: {
  children: ReactNode;
  tone?: TagTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-semibold uppercase leading-none",
        TAG_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Sello de verificacion: icono amarillo + texto corto. */
export function Seal({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-ink", className)}>
      <svg viewBox="0 0 24 24" aria-hidden className="size-[15px] shrink-0 fill-accent">
        <path d="M12 1.5l2.6 2.2 3.4-.3.6 3.4 2.9 1.8-1.5 3.1 1.5 3.1-2.9 1.8-.6 3.4-3.4-.3L12 22.5l-2.6-2.2-3.4.3-.6-3.4-2.9-1.8L4 12.3 2.5 9.2l2.9-1.8.6-3.4 3.4.3L12 1.5z" />
        <path d="M10.8 15.4l-3-3 1.3-1.3 1.7 1.7 4.1-4.1 1.3 1.3-5.4 5.4z" className="fill-ink" />
      </svg>
      {children}
    </span>
  );
}

/** Indicador "en directo": punto azul de 7px + texto de ayuda. */
export function LiveDot({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-[7px] text-help text-muted">
      <span aria-hidden className="block size-[7px] rounded-full bg-brand" />
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-control bg-line", className)} />;
}
