/** Como se pagara un contacto segun la cuenta. Funciones puras. */

import type { Account, Money } from "@/types/api";

/**
 * Minimo que la pasarela acepta cobrar. Espejo de `MIN_CHARGE_CENTS` del
 * backend, solo para anunciarlo: quien decide cuanto saldo se aplica es el API.
 */
export const MIN_CHARGE_CENTS = 50;

export type PurchasePlan =
  | { kind: "inactive" }
  | { kind: "debt"; debt: Money }
  | { kind: "credit" }
  | { kind: "mixed"; credit: Money; due: Money }
  | { kind: "checkout" };

export function purchasePlan(account: Account | null, price: Money): PurchasePlan {
  if (!account?.is_active) return { kind: "inactive" };
  // Una recarga devuelta por el banco que ya se gasto: el API rechaza la compra
  // hasta que la siguiente recarga salde la deuda.
  if (account.debt && account.debt.amount_cents > 0) return { kind: "debt", debt: account.debt };
  if (account.balance.currency !== price.currency || account.balance.amount_cents === 0) {
    return { kind: "checkout" };
  }
  let credit = Math.min(account.balance.amount_cents, price.amount_cents);
  const remainder = price.amount_cents - credit;
  if (remainder > 0 && remainder < MIN_CHARGE_CENTS) {
    credit = Math.max(0, price.amount_cents - MIN_CHARGE_CENTS);
  }
  if (credit === price.amount_cents) return { kind: "credit" };
  if (credit === 0) return { kind: "checkout" };
  const money = (cents: number): Money => ({
    amount_cents: cents,
    currency: price.currency,
    formatted: "",
  });
  return { kind: "mixed", credit: money(credit), due: money(price.amount_cents - credit) };
}
