import type { ReactNode } from "react";

import { cn } from "@/helpers/cn";

/**
 * Ancho de contenido del sistema: 1280px con 40px de margen lateral.
 *
 * `size="form"` estrecha a los 980px que el handoff fija para el formulario de
 * solicitud y para las pantallas de una sola columna.
 */
export function Container({
  children,
  size = "shell",
  className,
}: {
  children: ReactNode;
  size?: "shell" | "form";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto w-full px-5 sm:px-10",
        size === "form" ? "max-w-form" : "max-w-shell",
        className,
      )}
    >
      {children}
    </div>
  );
}
