"use client";

import { useTranslations } from "next-intl";

import { OptionCard } from "@/components/ui/OptionCard";
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
    <fieldset className="space-y-3">
      <legend className="text-[15px] font-semibold text-ink">
        {label}
        <span className="ml-0.5 text-danger">*</span>
      </legend>
      {hint && !error && <p className="text-help text-muted">{hint}</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => (
          <OptionCard
            key={category.id}
            name="category"
            value={category.id}
            title={category.name}
            checked={selected.includes(category.id)}
            onChange={toggle}
            type={multiple ? "checkbox" : "radio"}
          />
        ))}
      </div>

      {error && (
        <p role="alert" className="text-help font-medium text-danger">
          {error}
        </p>
      )}
      {categories.length === 0 && <p className="text-help text-muted">{t("loading")}</p>}
    </fieldset>
  );
}
