import type { ReactNode } from "react";

import { cn } from "@/helpers/cn";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 bg-white p-5 shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "brand" | "success" | "warning";
  className?: string;
}) {
  const tones = {
    neutral: "bg-slate-100 text-slate-700",
    brand: "bg-brand-100 text-brand-700",
    success: "bg-emerald-100 text-emerald-700",
    warning: "bg-accent-100 text-amber-800",
  } as const;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded bg-slate-200", className)} />;
}
