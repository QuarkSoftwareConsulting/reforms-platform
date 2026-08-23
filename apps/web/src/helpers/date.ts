/** Formateo de fechas. Funciones puras. */

import type { Locale } from "@/types/api";

const LOCALE_TAGS: Record<Locale, string> = { es: "es-ES", en: "en-US" };

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * "hace 3 horas" / "3 hours ago".
 *
 * En un marketplace de leads la antiguedad es informacion de negocio: un aviso de
 * hace dos horas vale mucho mas que uno de la semana pasada.
 */
export function formatRelative(iso: string, locale: Locale = "es", now = Date.now()): string {
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "";

  const elapsed = timestamp - now;
  const formatter = new Intl.RelativeTimeFormat(LOCALE_TAGS[locale], { numeric: "auto" });
  const absolute = Math.abs(elapsed);

  if (absolute < HOUR) return formatter.format(Math.round(elapsed / MINUTE), "minute");
  if (absolute < DAY) return formatter.format(Math.round(elapsed / HOUR), "hour");
  if (absolute < 30 * DAY) return formatter.format(Math.round(elapsed / DAY), "day");
  return formatter.format(Math.round(elapsed / (30 * DAY)), "month");
}

export function formatDate(iso: string, locale: Locale = "es"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(iso: string, locale: Locale = "es"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/** Minutos que quedan hasta `iso`, o 0 si ya paso. Para el TTL de la reserva. */
export function minutesUntil(iso: string | null, now = Date.now()): number {
  if (!iso) return 0;
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return 0;
  return Math.max(0, Math.ceil((target - now) / MINUTE));
}
