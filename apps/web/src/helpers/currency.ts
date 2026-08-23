/** Formateo de importes. Funciones puras, sin dependencias de React. */

import type { Locale, Money } from "@/types/api";

const ZERO_DECIMAL_CURRENCIES = new Set(["JPY", "KRW", "CLP"]);

const LOCALE_TAGS: Record<Locale, string> = { es: "es-ES", en: "en-US" };

/** Convierte centimos a la unidad mayor de la divisa. */
export function toUnits(amountCents: number, currency: string): number {
  return ZERO_DECIMAL_CURRENCIES.has(currency.toUpperCase())
    ? amountCents
    : amountCents / 100;
}

/**
 * Formatea un importe con las convenciones del idioma.
 *
 * Se usa `Intl` en vez de concatenar el simbolo: en espanol el euro va detras
 * ("5,00 €") y en ingles delante ("€5.00").
 */
export function formatMoney(money: Money, locale: Locale = "es"): string {
  const value = toUnits(money.amount_cents, money.currency);
  try {
    return new Intl.NumberFormat(LOCALE_TAGS[locale], {
      style: "currency",
      currency: money.currency,
      minimumFractionDigits: ZERO_DECIMAL_CURRENCIES.has(money.currency) ? 0 : 2,
    }).format(value);
  } catch {
    // Divisa desconocida por Intl: se cae al formato que ya trae el backend.
    return money.formatted;
  }
}

export function formatCents(amountCents: number, currency: string, locale: Locale = "es"): string {
  return formatMoney({ amount_cents: amountCents, currency, formatted: "" }, locale);
}
