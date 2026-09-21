"use client";

import { cn } from "@/helpers/cn";

export interface OptionCardProps {
  title: string;
  subtitle?: string;
  name: string;
  value: string;
  checked: boolean;
  onChange: (value: string) => void;
  type?: "radio" | "checkbox";
}

/**
 * Tarjeta de opcion: el control grande de eleccion del formulario.
 *
 * Igual que el chip, envuelve un `input` nativo oculto para no perder el rol ni
 * la etiqueta accesible. Los tests del asistente buscan justamente eso
 * (`getByRole("radio", { name: /Carpinteria/ })`).
 */
export function OptionCard({
  title,
  subtitle,
  name,
  value,
  checked,
  onChange,
  type = "radio",
}: OptionCardProps) {
  return (
    <label
      className={cn(
        "flex h-full cursor-pointer flex-col gap-1 rounded-option border-[1.5px] px-4 py-3.5",
        "text-left transition-colors",
        "focus-within:outline-none focus-within:ring-2 focus-within:ring-brand focus-within:ring-offset-2",
        checked
          ? "border-brand bg-brand-soft"
          : "border-line bg-surface hover:border-line-strong",
      )}
    >
      <input
        type={type}
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
        className="sr-only"
      />
      <span className="text-[15px] font-semibold text-ink">{title}</span>
      {subtitle && <span className="text-[12.5px] leading-[1.45] text-muted">{subtitle}</span>}
    </label>
  );
}
