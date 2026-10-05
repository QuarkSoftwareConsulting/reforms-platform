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

/** Zona horaria del negocio: el backend corta los dias del dashboard en ella. */
export const BUSINESS_TIME_ZONE = "Europe/Madrid";

/**
 * Ultimos `days` dias naturales en la zona del negocio, ambos incluidos, como
 * `YYYY-MM-DD`. Se calcula en Madrid y no en la zona del navegador para que un
 * admin de viaje pida los mismos dias que ve el resto.
 */
export function lastDaysRange(
  days: number,
  now = Date.now(),
  timeZone = BUSINESS_TIME_ZONE,
): { from: string; to: string } {
  // `en-CA` formatea como YYYY-MM-DD.
  const to = new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date(now));
  const start = new Date(`${to}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { from: start.toISOString().slice(0, 10), to };
}

/** "3 mar" / "Mar 3" para un dia `YYYY-MM-DD`, sin desplazarlo por la zona horaria. */
export function formatDay(day: string, locale: Locale = "es"): string {
  const date = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(LOCALE_TAGS[locale], {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(date);
}

/** Valor para un `<input type="datetime-local">`: hora local, sin zona y sin segundos. */
export function toDatetimeLocal(date: Date): string {
  const pad = (value: number): string => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}
