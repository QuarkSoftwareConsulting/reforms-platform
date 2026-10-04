"use client";

import { useId } from "react";

import { FieldError } from "@/components/ui/Field";
import { cn } from "@/helpers/cn";

export interface ChipOption<T extends string = string> {
  value: T;
  label: string;
}

/**
 * Grupo de chips de seleccion (sistema de diseno, "Chip de seleccion").
 *
 * Cada chip envuelve un `input` nativo oculto, como `OptionCard`: se conservan el
 * rol (radio o checkbox), la etiqueta accesible y la navegacion por teclado.
 */
export function ChipGroup<T extends string>({
  name,
  label,
  hint,
  options,
  selected,
  onToggle,
  multiple = false,
  required = false,
  error,
  className,
  fieldKey,
}: {
  name: string;
  label: string;
  hint?: string;
  options: ChipOption<T>[];
  selected: T[];
  onToggle: (value: T) => void;
  multiple?: boolean;
  required?: boolean;
  error?: string;
  className?: string;
  /** Clave con la que `FormErrorSummary` encuentra el grupo para llevar el foco. */
  fieldKey?: string;
}) {
  const errorId = useId();
  return (
    // `tabIndex={-1}`: el resumen de errores puede enfocar el grupo aunque no sea un control.
    <fieldset
      className={cn("space-y-3 focus:outline-none", className)}
      data-field={fieldKey}
      tabIndex={fieldKey ? -1 : undefined}
      aria-describedby={error ? errorId : undefined}
    >
      <legend className="text-[15px] font-semibold text-ink">
        {label}
        {required && (
          <span aria-hidden className="ml-0.5 text-danger">
            *
          </span>
        )}
      </legend>
      {hint && !error && <p className="text-help text-muted">{hint}</p>}

      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const checked = selected.includes(option.value);
          return (
            <label
              key={option.value}
              className={cn(
                "cursor-pointer rounded-full border-[1.5px] px-4 py-2.5 text-[14.5px] transition-colors",
                "focus-within:outline-none focus-within:ring-2 focus-within:ring-brand focus-within:ring-offset-2",
                checked
                  ? "border-brand bg-brand font-medium text-surface"
                  : "border-line bg-surface text-ink hover:border-line-strong",
              )}
            >
              <input
                type={multiple ? "checkbox" : "radio"}
                name={name}
                value={option.value}
                checked={checked}
                onChange={() => onToggle(option.value)}
                // En un grupo de radios, `required` es lo que anuncia "obligatorio".
                required={required && !multiple}
                className="sr-only"
              />
              {option.label}
            </label>
          );
        })}
      </div>

      {error && <FieldError id={errorId}>{error}</FieldError>}
    </fieldset>
  );
}
