import type { ReactNode } from "react";

import { cn } from "@/helpers/cn";

type Tone = "info" | "success" | "warning" | "error";

const TONES: Record<Tone, string> = {
  info: "bg-brand-50 text-brand-900 border-brand-200",
  success: "bg-emerald-50 text-emerald-900 border-emerald-200",
  warning: "bg-accent-50 text-amber-900 border-accent-100",
  error: "bg-red-50 text-red-900 border-red-200",
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
      className={cn("rounded-lg border px-4 py-3 text-sm", TONES[tone], className)}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={cn(title && "mt-1")}>{children}</div>}
    </div>
  );
}
