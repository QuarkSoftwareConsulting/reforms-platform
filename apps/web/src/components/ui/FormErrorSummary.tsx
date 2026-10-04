"use client";

import { useEffect, useRef } from "react";

import { Alert } from "@/components/ui/Alert";

export interface SummaryIssue {
  /** Clave del campo (`fieldKey`): la que `onSelect` usa para llevar el foco. */
  field: string;
  label: string;
  message: string;
}

/**
 * Lista de los campos a corregir, para ponerla junto al boton de enviar.
 *
 * En un formulario largo el usuario pulsa "Guardar" abajo y el error esta arriba, fuera
 * de pantalla: parece que el boton no hace nada. El resumen vive donde esta el usuario y
 * cada campo es un enlace que lo lleva hasta el. El error sigue tambien junto al campo.
 *
 * `attempt` sube en cada envio fallido: entonces el resumen toma el foco (y entra en
 * pantalla). Con solo cambiar la lista, por ejemplo al corregir un campo, no lo roba.
 */
export function FormErrorSummary({
  title,
  issues,
  onSelect,
  attempt,
}: {
  title: string;
  issues: SummaryIssue[];
  onSelect: (field: string) => void;
  attempt: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const hasIssues = useRef(false);

  useEffect(() => {
    hasIssues.current = issues.length > 0;
  }, [issues.length]);

  useEffect(() => {
    if (attempt > 0 && hasIssues.current) ref.current?.focus();
  }, [attempt]);

  if (issues.length === 0) return null;

  return (
    <div ref={ref} tabIndex={-1} className="rounded-control focus:outline-none focus:shadow-focus">
      <Alert tone="error" title={title}>
        <ul className="space-y-1">
          {issues.map((issue) => (
            <li key={issue.field}>
              <button
                type="button"
                onClick={() => onSelect(issue.field)}
                className="text-left font-semibold underline underline-offset-2 hover:no-underline"
              >
                {issue.label}
              </button>
              <span>: {issue.message}</span>
            </li>
          ))}
        </ul>
      </Alert>
    </div>
  );
}
