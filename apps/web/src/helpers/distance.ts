/** Presentacion de distancias. */

import type { Locale } from "@/types/api";

/**
 * Redondea a algo legible: por debajo de 1 km se dice "menos de 1 km" en vez de
 * dar una precision de metros que el centroide del codigo postal no tiene.
 */
export function formatDistance(km: number | null, locale: Locale = "es"): string {
  if (km === null || Number.isNaN(km)) return "";
  if (km < 1) return locale === "en" ? "less than 1 km" : "menos de 1 km";
  const rounded = km < 10 ? Math.round(km * 10) / 10 : Math.round(km);
  return `${rounded.toLocaleString(locale === "en" ? "en-US" : "es-ES")} km`;
}
