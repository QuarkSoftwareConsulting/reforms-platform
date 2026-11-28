/**
 * Saldo del profesional a la vista (informe de pruebas del 22-11, punto 15).
 *
 * El fallo: el saldo solo aparecia en el aviso de /proyectos (y solo con la cuenta
 * activa) y en /suscripcion. Con 0 € o la recarga caducada parecia haber desaparecido,
 * y en el perfil no estaba.
 */

import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Account, Money } from "@/types/api";

let auth: { isAuthenticated: boolean; me: { role: string; account: Account | null } | null };

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => <span data-testid="img" aria-label={alt} />,
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/es/proyectos" }));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ ...auth, logout: vi.fn() }) }));

const { SiteHeader } = await import("@/components/features/SiteHeader");
const { BalanceCard } = await import("@/components/features/profile/BalanceCard");
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

/** Texto del indicador de la cabecera, partido en "Saldo: " + importe. */
const balanceLink = (amount: string) =>
  screen.getAllByRole("link", {
    name: `${messages.nav.balance.split("{balance}")[0]}${amount}`,
    hidden: true,
  });

describe("SiteHeader: saldo", () => {
  beforeEach(() => {
    auth = { isAuthenticated: true, me: { role: "professional", account: account() } };
  });

  it("shows a zero balance linking to the subscription page", () => {
    renderWithIntl(<SiteHeader />);
    const links = balanceLink("0,00\u00a0€");
    // Una en la barra de escritorio y otra en el menu movil.
    expect(links).toHaveLength(2);
    for (const link of links) expect(link.getAttribute("href")).toBe("/es/suscripcion");
  });

  it("keeps showing the balance of an inactive account", () => {
    auth.me = {
      role: "professional",
      account: account({ status: "past_due", is_active: false, balance: eur(2500) }),
    };
    renderWithIntl(<SiteHeader />);
    expect(balanceLink("25,00\u00a0€")).toHaveLength(2);
  });

  it("shows nothing without a professional account", () => {
    auth.me = { role: "admin", account: null };
    renderWithIntl(<SiteHeader />);
    expect(screen.queryByText(/Saldo/)).toBeNull();
  });

  it("shows nothing to a visitor", () => {
    auth = { isAuthenticated: false, me: null };
    renderWithIntl(<SiteHeader />);
    expect(screen.queryByText(/Saldo/)).toBeNull();
  });
});

describe("BalanceCard (perfil)", () => {
  it("shows a zero balance and links to the subscription page", () => {
    renderWithIntl(<BalanceCard account={account({ status: "canceled", is_active: false })} />);
    expect(screen.getByText(messages.subscription.balanceLabel)).toBeDefined();
    expect(screen.getByText(/^0,00\s€$/)).toBeDefined();
    const link = screen.getByRole("link", { name: messages.subscription.bannerManage });
    expect(link.getAttribute("href")).toBe("/es/suscripcion");
  });
});
