"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/helpers/cn";
import type { Category } from "@/types/api";

/** Selector de oficios: uno solo (radio) o varios (checkbox). */
export function CategoryPicker({
  categories,
  selected,
  onChange,
  multiple = false,
  error,
  label,
  hint,
}: {
  categories: Category[];
  selected: string[];
  onChange: (ids: string[]) => void;
  multiple?: boolean;
  error?: string;
  label: string;
  hint?: string;
}) {
  const t = useTranslations("common");

  const toggle = (id: string) => {
    if (!multiple) {
      onChange([id]);
      return;
    }
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-slate-800">
        {label}
        <span className="ml-0.5 text-red-600">*</span>
      </legend>
      {hint && !error && <p className="text-sm text-slate-500">{hint}</p>}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {categories.map((category) => {
          const isSelected = selected.includes(category.id);
          return (
            <label
              key={category.id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm",
                "transition-colors hover:border-brand-400",
                isSelected
                  ? "border-brand-600 bg-brand-50 font-medium text-brand-900"
                  : "border-slate-300 bg-white text-slate-700",
              )}
            >
              <input
                type={multiple ? "checkbox" : "radio"}
                name="category"
                value={category.id}
                checked={isSelected}
                onChange={() => toggle(category.id)}
                className="size-4 text-brand-600 focus:ring-brand-200"
              />
              <span className="truncate">{category.name}</span>
            </label>
          );
        })}
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      {categories.length === 0 && <p className="text-sm text-slate-500">{t("loading")}</p>}
    </fieldset>
  );
}
