/**
 * Opciones cerradas del formulario de publicacion (F01, paso 2).
 *
 * Reflejan los enums del backend (`PropertyType`, `ProjectSchedule`): el API rechaza
 * cualquier otro valor. Las etiquetas viven en `messages/*.json`, por codigo.
 */

export const PROPERTY_TYPES = [
  "flat",
  "house",
  "commercial",
  "office",
  "community",
  "industrial",
  "land",
] as const;
export type PropertyType = (typeof PROPERTY_TYPES)[number];

export const PROJECT_SCHEDULES = [
  "asap",
  "within_weeks",
  "within_months",
  "gathering_quotes",
] as const;
export type ProjectSchedule = (typeof PROJECT_SCHEDULES)[number];
