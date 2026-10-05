/**
 * Recarga mensual en el front.
 *
 * Lo que se vigila: una cuenta inactiva nunca ve el boton de compra como si
 * pudiera comprar, y el anuncio de cuanto saldo se aplicara coincide con la
 * regla del backend (incluido el minimo de la pasarela).
 */

import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { purchasePlan } from "@/helpers/credit";
import type { Account, Money } from "@/types/api";

import enMessages from "../messages/en.json";

const { AccountStatusBanner } = await import("@/components/features/AccountStatusBanner");
const { renderWithIntl, messages } = await import("./render");

const eur = (cents: number): Money => ({ amount_cents: cents, currency: "EUR", formatted: "" });

function account(overrides: Partial<Account> = {}): Account {
  return {
    status: "active",
    is_active: true,
    balance: eur(0),
    topup_amount: eur(1800),
    current_period_end: null,
    can_manage_billing: true,
    entries: [],
    ...overrides,
  };
}

describe("purchasePlan", () => {
  it("blocks the purchase without an active top-up, even with balance", () => {
    expect(purchasePlan(null, eur(1800))).toEqual({ kind: "inactive" });
    expect(
      purchasePlan(account({ status: "past_due", is_active: false, balance: eur(5000) }), eur(1800)),
    ).toEqual({ kind: "inactive" });
  });

  it("pays entirely with balance when it covers the price", () => {
    expect(purchasePlan(account({ balance: eur(1800) }), eur(1800))).toEqual({ kind: "credit" });
  });

  it("splits balance and checkout when short", () => {
    expect(purchasePlan(account({ balance: eur(1000) }), eur(1800))).toEqual({
      kind: "mixed",
      credit: eur(1000),
      due: eur(800),
    });
  });

  it("leaves at least the gateway minimum for checkout", () => {
    const plan = purchasePlan(account({ balance: eur(1780) }), eur(1800));
    expect(plan).toEqual({ kind: "mixed", credit: eur(1750), due: eur(50) });
  });

  it("goes to checkout with no balance", () => {
    expect(purchasePlan(account(), eur(1800))).toEqual({ kind: "checkout" });
  });

  it("cannot buy while a returned top-up is still owed", () => {
    // La recarga sigue al dia, pero el banco devolvio una ya gastada: el API rechaza.
    expect(purchasePlan(account({ debt: eur(1300) }), eur(500))).toEqual({
      kind: "debt",
      debt: eur(1300),
    });
  });
});

describe("AccountStatusBanner", () => {
  it("shows the balance of an active account", () => {
    renderWithIntl(<AccountStatusBanner account={account({ balance: eur(1800) })} />);
    expect(screen.getByRole("status").textContent).toContain("18,00");
  });

  it("warns an inactive account that it can browse but not buy", () => {
    renderWithIntl(<AccountStatusBanner account={account({ status: "none", is_active: false })} />);
    expect(screen.getByRole("alert").textContent).toContain(messages.subscription.bannerInactive);
    const link = screen.getByRole("link", { name: messages.subscription.bannerCta });
    expect(link.getAttribute("href")).toBe("/es/suscripcion");
  });

  it("warns an active account with debt that it cannot buy yet", () => {
    renderWithIntl(<AccountStatusBanner account={account({ debt: eur(1300) })} />);
    const text = screen.getByRole("alert").textContent ?? "";
    expect(text).toContain(messages.subscription.bannerDebt.split("{debt}")[0]);
    expect(text).toContain("13,00");
  });

  it("treats a professional without account as inactive", () => {
    renderWithIntl(<AccountStatusBanner account={null} />);
    expect(screen.getByRole("alert").textContent).toContain(messages.subscription.status.none);
  });
});

describe("translations", () => {
  function keys(node: unknown, prefix = ""): string[] {
    if (typeof node !== "object" || node === null) return [prefix];
    return Object.entries(node).flatMap(([key, value]) =>
      keys(value, prefix ? `${prefix}.${key}` : key),
    );
  }

  it("has the same keys in Spanish and English", () => {
    expect(keys(enMessages).sort()).toEqual(keys(messages).sort());
  });
});
