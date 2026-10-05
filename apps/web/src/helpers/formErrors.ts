/**
 * Errores de formulario: lectura de los errores de campo del backend y foco en el
 * campo que hay que corregir. Funciones puras, sin React.
 */

/** Un error atado a un campo del formulario. `field` es la clave del campo (`data-field`). */
export interface FormIssue {
  field: string;
  message: string;
}

/** Un error de campo del esquema Pydantic (`details.errors` del backend). */
export interface SchemaIssue {
  /** Ruta del campo sin indices y con `_`: `consent.accepted_at` es `consent_accepted_at`. */
  key: string;
  type: string;
  limits: Record<string, number>;
}

function numericLimits(raw: unknown): Record<string, number> {
  const limits: Record<string, number> = {};
  if (typeof raw !== "object" || raw === null) return limits;
  for (const [name, value] of Object.entries(raw)) {
    if (typeof value === "number") limits[name] = value;
  }
  return limits;
}

export function schemaIssues(details: Record<string, unknown> | null): SchemaIssue[] {
  const raw = details?.errors;
  if (!Array.isArray(raw)) return [];
  const issues: SchemaIssue[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const { field, type, limits } = item as Record<string, unknown>;
    if (typeof field !== "string") continue;
    // "photo_keys.0" es la foto 0 del campo "photo_keys": el indice no se nombra.
    const key = field
      .split(".")
      .filter((part) => !/^\d+$/.test(part))
      .join("_");
    if (!key) continue;
    issues.push({ key, type: typeof type === "string" ? type : "", limits: numericLimits(limits) });
  }
  return issues;
}

/**
 * Lleva el foco (y la vista) al campo con esa clave dentro de `root`.
 *
 * En un formulario largo el error suele estar fuera de pantalla: el resumen junto al
 * boton llama a esto para que el usuario no tenga que buscarlo. Sin `scrollIntoView`
 * (jsdom) solo mueve el foco.
 */
export function focusField(root: ParentNode | null, field: string): void {
  if (!root || !/^[\w-]+$/.test(field)) return;
  const element = root.querySelector<HTMLElement>(`[data-field="${field}"]`);
  if (!element) return;
  const reduceMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  element.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  // `preventScroll`: el scroll ya lo hace la linea de arriba, con su animacion.
  element.focus({ preventScroll: true });
}
