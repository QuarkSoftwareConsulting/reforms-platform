/**
 * Detalle de una solicitud antes de pagar.
 *
 * Lo que se vigila: un lead cerrado se puede consultar pero nunca ofrece comprar,
 * y el precio se anuncia con el IVA incluido y desglosado.
 */

import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadDetail, LeadPublic } from "@/types/api";

const detailMock = vi.fn<(id: string, locale: string) => Promise<LeadDetail>>();

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => <span data-testid="img" aria-label={alt} />,
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("@/services/leads.service", () => ({ leadsService: { detail: detailMock } }));
const verification = { status: "approved" };
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    me: {
      professional: { verification },
      account: {
        status: "active",
        is_active: true,
        balance: { amount_cents: 0, currency: "EUR", formatted: "0.00 €" },
      },
    },
  }),
}));
vi.mock("@/hooks/useLeadPurchase", () => ({
  useLeadPurchase: () => ({ pending: false, error: null, start: vi.fn() }),
}));

const { LeadDetailView } = await import("@/components/features/LeadDetailView");
const { renderWithIntl, messages } = await import("./render");

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

function detail(lead: Partial<LeadPublic> = {}): LeadDetail {
  return { lead: { ...LEAD, ...lead }, is_unlocked: false, contact: null, purchase: null };
}

describe("LeadDetailView", () => {
  beforeEach(() => {
    detailMock.mockReset();
    verification.status = "approved";
  });

  it("shows first name, postcode, buyers and the VAT breakdown before paying", async () => {
    detailMock.mockResolvedValue(detail());
    renderWithIntl(<LeadDetailView leadId="lead-1" />);

    expect(await screen.findByText("Ana")).toBeDefined();
    expect(screen.getByText("28001")).toBeDefined();
    expect(screen.getByText("2 de 5 profesionales ya lo compraron")).toBeDefined();
    expect(screen.getByText(messages.project.propertyTypes.flat)).toBeDefined();
    expect(screen.getByText(messages.project.schedules.asap)).toBeDefined();
    expect(screen.getByText("Armarios a medida")).toBeDefined();
    const vat = /IVA incluido · Base imponible 4,13\s€ \+ IVA \(21 %\) 0,87\s€/;
    expect(screen.getByText(vat)).toBeDefined();
    expect(screen.getByRole("button", { name: /Comprar contacto/ })).toBeDefined();
  });

  it("shows a closed lead without any way to buy it", async () => {
    detailMock.mockResolvedValue(
      detail({ is_closed: true, remaining_slots: 0, purchases_count: 5 }),
    );
    renderWithIntl(<LeadDetailView leadId="lead-1" />);

    expect(await screen.findByText(messages.lead.closedTitle)).toBeDefined();
    expect(screen.getByText(messages.projects.closed)).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("does not offer to buy until the registration is approved", async () => {
    verification.status = "pending";
    detailMock.mockResolvedValue(detail());
    renderWithIntl(<LeadDetailView leadId="lead-1" />);

    expect(await screen.findByText(messages.lead.needsApprovalPending)).toBeDefined();
    expect(screen.queryByRole("button", { name: /Comprar contacto/ })).toBeNull();
    expect(screen.getByRole("link", { name: messages.lead.completeRegistration })).toBeDefined();
  });
});
