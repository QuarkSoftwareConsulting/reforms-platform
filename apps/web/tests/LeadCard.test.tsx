/**
 * Test de la tarjeta del explorador.
 *
 * El invariante que se vigila: la tarjeta no puede renderizar datos de contacto
 * del cliente bajo ninguna circunstancia.
 */

import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { LeadPublic } from "@/types/api";

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => <span data-testid="img" aria-label={alt} />,
}));

const { LeadCard } = await import("@/components/features/LeadCard");
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
  photo_urls: ["https://cdn.test/a.jpg"],
  created_at: new Date(Date.now() - 3 * 3600_000).toISOString(),
  remaining_slots: 2,
  purchases_count: 3,
  max_purchases: 5,
  is_closed: false,
  distance_km: 12.4,
  masked_phone: "*********44",
  masked_email: "a****@example.com",
  already_purchased: false,
  price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
  price_breakdown: {
    net: { amount_cents: 413, currency: "EUR", formatted: "4.13 €" },
    vat: { amount_cents: 87, currency: "EUR", formatted: "0.87 €" },
    rate_percent: 21,
  },
};

describe("LeadCard", () => {
  it("shows the trade, city and distance", () => {
    renderWithIntl(<LeadCard lead={LEAD} />);

    expect(screen.getByText("Carpinteria")).toBeDefined();
    expect(screen.getByText(/Madrid/)).toBeDefined();
    // A 12 km un decimal seria precision falsa: el centroide del CP no la tiene.
    expect(screen.getByText(/12 km/)).toBeDefined();
  });

  it("never renders unmasked client contact details", () => {
    const { container } = renderWithIntl(<LeadCard lead={LEAD} />);
    const html = container.innerHTML;

    expect(html).not.toContain("611223344");
    expect(html).not.toContain("@example.com");
    expect(html).not.toContain("Ana Lopez");
  });

  it("warns when only one slot is left", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, remaining_slots: 1 }} />);
    expect(screen.getByText(/Queda 1 plaza/)).toBeDefined();
  });

  it("marks leads already purchased", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, already_purchased: true }} />);
    expect(screen.getByText(messages.projects.purchased)).toBeDefined();
  });

  it("formats the price with the Spanish convention", () => {
    renderWithIntl(<LeadCard lead={LEAD} />);
    expect(screen.getByText(/5,00/)).toBeDefined();
  });

  it("renders without a cover photo", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, photo_urls: [] }} />);
    expect(screen.queryByTestId("img")).toBeNull();
    expect(screen.getByText(LEAD.title)).toBeDefined();
  });

  it("shows the client's first name and postcode but never the surname", () => {
    const { container } = renderWithIntl(<LeadCard lead={LEAD} />);

    expect(screen.getByText("Cliente: Ana")).toBeDefined();
    expect(screen.getByText(/28001 Madrid/)).toBeDefined();
    expect(container.innerHTML).not.toContain("Lopez");
  });

  it("hides the first name when the client's consent does not cover it", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, client_first_name: null, postal_code: null }} />);
    expect(screen.queryByText(/Cliente:/)).toBeNull();
    expect(screen.queryByText(/28001/)).toBeNull();
  });

  it("tells how many professionals already bought it", () => {
    renderWithIntl(<LeadCard lead={LEAD} />);
    expect(screen.getByText("3 profesionales ya lo compraron")).toBeDefined();
  });

  it("states that the price includes VAT", () => {
    renderWithIntl(<LeadCard lead={LEAD} />);
    expect(screen.getByText(messages.projects.vatIncluded)).toBeDefined();
  });

  it("shows exhausted leads as closed, without a link to buy", () => {
    const closed = { ...LEAD, is_closed: true, remaining_slots: 0, purchases_count: 5 };
    renderWithIntl(<LeadCard lead={closed} />);
    expect(screen.getByText(messages.projects.closed)).toBeDefined();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("keeps the link for whoever already bought a closed lead", () => {
    renderWithIntl(
      <LeadCard
        lead={{
          ...LEAD,
          is_closed: true,
          remaining_slots: 0,
          purchases_count: 5,
          already_purchased: true,
        }}
      />,
    );
    expect(screen.queryByText(messages.projects.closed)).toBeNull();
    expect(screen.getByRole("link")).toBeDefined();
  });

  it("shows the chosen services, property type and timing", () => {
    renderWithIntl(<LeadCard lead={LEAD} />);
    expect(screen.getByText("Armarios a medida")).toBeDefined();
    const project = `${messages.project.propertyTypes.flat} · ${messages.project.schedules.asap}`;
    expect(screen.getByText(project)).toBeDefined();
  });

  it("renders older leads that have no project data", () => {
    renderWithIntl(
      <LeadCard lead={{ ...LEAD, services: [], property_type: null, schedule: null }} />,
    );
    expect(screen.queryByText(messages.project.propertyTypes.flat)).toBeNull();
    expect(screen.getByText(LEAD.title)).toBeDefined();
  });

  it("omits distance when it is unknown", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, distance_km: null }} />);
    expect(screen.queryByText(/km/)).toBeNull();
  });
});
