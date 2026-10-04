"use client";

import { Button } from "@/components/ui/Button";

/** Anterior / Siguiente con el texto de la pagina actual. Las etiquetas llegan traducidas. */
export function Pagination({
  page,
  pages,
  label,
  previous,
  next,
  onChange,
}: {
  /** Base 0. */
  page: number;
  pages: number;
  label: string;
  previous: string;
  next: string;
  onChange: (page: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <nav className="flex items-center justify-between gap-3" aria-label={label}>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
      >
        {previous}
      </Button>
      <span className="text-help text-muted">{label}</span>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={page >= pages - 1}
        onClick={() => onChange(page + 1)}
      >
        {next}
      </Button>
    </nav>
  );
}
