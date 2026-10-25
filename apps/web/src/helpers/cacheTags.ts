/**
 * Etiquetas de la cache de Next para los datos que cambia el admin.
 *
 * Las paginas publicas (landing, formulario) se sirven estaticas: se regeneran al
 * momento cuando el admin guarda un cambio (`/api/revalidate` invalida la etiqueta) y,
 * como respaldo si esa llamada fallara, una vez al dia.
 */

export const CATALOG_TAG = "catalog";
export const PRICING_TAG = "pricing";

export type CacheTag = typeof CATALOG_TAG | typeof PRICING_TAG;

export const CACHE_TAGS: readonly CacheTag[] = [CATALOG_TAG, PRICING_TAG];

/** Respaldo: aunque nadie invalide, la pagina no queda mas de un dia desfasada. */
export const DAILY_REVALIDATE_SECONDS = 24 * 60 * 60;
