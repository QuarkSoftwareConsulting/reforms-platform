/**
 * Despues de comprar, el contacto se ve en la propia solicitud.
 *
 * El fallo que cubren: comprar con saldo recargaba la pagina hacia "Mis contactos" y
 * una carrera de la sesion acababa en /perfil. Y al volver de Stripe, mientras llegaba
 * el webhook, el detalle ofrecia pagar otra vez una reserva ya pagada.
 */

import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadDetail, LeadPublic } from "@/types/api";

const detailMock = vi.fn<(id: string, locale: string) => Promise<LeadDetail>>();
const startPurchase = vi.fn();
const refreshMe = vi.fn();
const assign = vi.fn();
let search = new URLSearchParams();

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => <span data-testid="img" aria-label={alt} />,
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/services/leads.service", () => ({ leadsService: { detail: detailMock } }));
vi.mock("@/services/payment.service", () => ({
  paymentService: { startPurchase: (...args: unknown[]) => startPurchase(...args) },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    refreshMe,
    me: {
      professional: { verification: { status: "approved" } },
      account: {
        status: "active",
        is_active: true,
        balance: { amount_cents: 1000, currency: "EUR", formatted: "10.00 €" },
        debt: null,
      },
    },
  }),
}));

const { LeadDetailView } = await import("@/components/features/LeadDetailView");
const { renderWithIntl, messages } = await import("./render");

const t = messages.lead;

const LEAD: LeadPublic = {
  id: "lead-1",
  title: "Reparar armario de cocina",
  description: "Se ha descolgado la puerta del armario alto.",
  city: "Madrid",
  province: "Madrid",
  postal_code_prefix: "28",
  postal_code: "28001",
  client_first_name: "Ana",
  category: {
    id: "cat-1",
    slug: "carpinteria",
    name: "Carpinteria",
    suggested_lead_price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
  },
  services: [{ id: "svc-1", slug: "armarios", name: "Armarios a medida" }],
  property_type: "flat",
  schedule: "asap",
  photo_urls: [],
  created_at: new Date().toISOString(),
  remaining_slots: 3,
  purchases_count: 2,
  max_purchases: 5,
  is_closed: false,
  distance_km: 2,
  masked_phone: "*********44",
  masked_email: null,
  already_purchased: false,
  price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
  price_breakdown: {
    net: { amount_cents: 413, currency: "EUR", formatted: "4.13 €" },
    vat: { amount_cents: 87, currency: "EUR", formatted: "0.87 €" },
    rate_percent: 21,
  },
};

const CONTACT = { name: "Ana Lopez", phone: "+34611223344", email: "ana@example.com" };

const locked = (): LeadDetail => ({
  lead: LEAD,
  is_unlocked: false,
  contact: null,
  purchase: null,
});
const unlocked = (): LeadDetail => ({
  lead: LEAD,
  is_unlocked: true,
  contact: CONTACT,
  purchase: null,
});

/** "Comprar contacto por {price}": se busca por el texto del mensaje, sin el precio. */
const UNLOCK = new RegExp(`^${t.unlock.split("{price}")[0]}`);
const unlockButton = () => screen.queryByRole("button", { name: UNLOCK });

describe("LeadDetailView: despues de comprar", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    detailMock.mockReset();
    startPurchase.mockReset();
    refreshMe.mockReset();
    assign.mockReset();
    search = new URLSearchParams();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { assign, href: "http://localhost/" },
    });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the contact right there when the balance paid it, without leaving the page", async () => {
    detailMock.mockResolvedValueOnce(locked()).mockResolvedValue(unlocked());
    startPurchase.mockResolvedValue({ purchase_id: "purchase-1", checkout_url: null });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithIntl(<LeadDetailView leadId={LEAD.id} />);

    await user.click(await screen.findByRole("button", { name: UNLOCK }));

    expect(await screen.findByText(CONTACT.phone)).toBeDefined();
    expect(screen.getByText(t.purchaseConfirmed)).toBeDefined();
    expect(assign).not.toHaveBeenCalled();
    // El saldo cambio: se refresca la sesion sin desmontar la pagina.
    expect(refreshMe).toHaveBeenCalledWith({ silent: true });
  });

  it("waits for the payment after Stripe instead of offering to pay again", async () => {
    search = new URLSearchParams("purchase=purchase-1&status=success");
    detailMock
      .mockResolvedValueOnce({
        ...locked(),
        purchase: {
          id: "purchase-1",
          status: "reserved",
          amount: LEAD.price,
          created_at: new Date().toISOString(),
          paid_at: null,
          reserved_until: new Date(Date.now() + 20 * 60_000).toISOString(),
        },
      })
      .mockResolvedValue(unlocked());
    renderWithIntl(<LeadDetailView leadId={LEAD.id} />);

    expect(await screen.findByText(t.purchaseConfirming)).toBeDefined();
    expect(unlockButton()).toBeNull();
    expect(screen.queryByRole("button", { name: t.resumePayment })).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });

    expect(await screen.findByText(CONTACT.phone)).toBeDefined();
    expect(screen.getByText(t.purchaseConfirmed)).toBeDefined();
  });

  it("asks for patience and lets the user check again when confirmation is slow", async () => {
    search = new URLSearchParams("purchase=purchase-1&status=success");
    detailMock.mockResolvedValue(locked());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithIntl(<LeadDetailView leadId={LEAD.id} />);
    await screen.findByText(t.purchaseConfirming);

    for (let i = 0; i < 8; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2500);
      });
    }

    expect(await screen.findByText(t.purchaseDelayed)).toBeDefined();
    expect(unlockButton()).toBeNull();
    const calls = detailMock.mock.calls.length;
    await user.click(screen.getByRole("button", { name: t.checkAgain }));
    expect(detailMock.mock.calls.length).toBe(calls + 1);
  });
});
