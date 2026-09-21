import type { ReactNode } from "react";

import { cn } from "@/helpers/cn";

type Tone = "info" | "success" | "warning" | "error";

/**
 * El sistema solo define color de estado para el error (§8 del handoff deja
 * abiertos el resto). Hasta que se decidan, el informativo usa el azul suave de
 * marca y aviso y exito se apoyan en el acento y en el azul, sin inventar
 * colores nuevos.
 */
const TONES: Record<Tone, string> = {
  info: "border-brand-soft bg-brand-soft text-ink",
  success: "border-line bg-page text-ink",
  warning: "border-accent bg-accent-disabled text-ink",
  error: "border-danger bg-danger-bg text-danger",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      // `role="alert"` solo en los tonos que interrumpen: un aviso informativo no
      // debe robarle el foco al lector de pantalla.
      role={tone === "error" || tone === "warning" ? "alert" : "status"}
      className={cn("rounded-control border px-4 py-3 text-[14.5px]", TONES[tone], className)}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={cn(title && "mt-1")}>{children}</div>}
    </div>
  );
}
