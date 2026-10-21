/**
 * Reglas del formulario del catalogo. Duplican a proposito las del backend
 * (`app/domain/models/category.py`) para responder al momento; el API revalida.
 */

/** Limites de las columnas en la BD. */
export const CATEGORY_NAME_MAX = 120;
export const SERVICE_NAME_MAX = 160;
/** Nombre corto de la tarjeta de la landing: espejo de `LANDING_NAME_MAX_LENGTH`. */
export const LANDING_NAME_MAX = 40;
/** Tope de seguridad del precio de un contacto: espejo de `MAX_SALE_PRICE_CENTS`. */
export const MAX_PRICE_CENTS = 100_000;

export type CatalogFieldError =
  | "catalogNameRequired"
  | "catalogNameTooLong"
  | "catalogPrice"
  | "catalogSortOrder"
  | "catalogPhotoRequired"
  | "catalogPhotoType"
  | "catalogPhotoSize";

/** Fotos de las tarjetas de la landing: espejo de `CATALOG_IMAGE_TYPES` del backend. */
export const CATALOG_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const CATALOG_IMAGE_MAX_BYTES = 5 * 1024 * 1024;

export function photoError(file: File): CatalogFieldError | null {
  if (!(CATALOG_IMAGE_TYPES as readonly string[]).includes(file.type)) return "catalogPhotoType";
  return file.size > CATALOG_IMAGE_MAX_BYTES ? "catalogPhotoSize" : null;
}

/** El nombre tal como lo guarda el backend: sin espacios sobrantes. */
export function cleanName(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

export function nameError(value: string, max: number): CatalogFieldError | null {
  const cleaned = cleanName(value);
  // Sin una letra o un numero no hay slug posible: el backend lo rechazaria.
  if (!/[\p{L}\p{N}]/u.test(cleaned)) return "catalogNameRequired";
  return cleaned.length > max ? "catalogNameTooLong" : null;
}

/** Nombre corto opcional: vacio vale (se usa el del servicio); si no, como un nombre. */
export function landingNameError(value: string): CatalogFieldError | null {
  return cleanName(value) ? nameError(value, LANDING_NAME_MAX) : null;
}

/** El nombre corto tal como se envia: `null` si se dejo vacio. */
export function landingNameValue(value: string): string | null {
  return cleanName(value) || null;
}

/** "12,50" o "12.5" en euros -> 1250 centimos; `null` si no es un precio valido. */
export function parsePriceCents(raw: string): number | null {
  const normalized = raw.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  const cents = Math.round(Number(normalized) * 100);
  return cents > 0 && cents <= MAX_PRICE_CENTS ? cents : null;
}

/** 1250 -> "12,50": el valor inicial del campo de precio al editar. */
export function priceInput(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",");
}

/** Orden del catalogo: entero de 0 a 10000, como el backend. */
export function parseSortOrder(raw: string): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw.trim());
  return value <= 10_000 ? value : null;
}
