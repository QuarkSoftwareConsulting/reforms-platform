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
  category: {
    id: "cat-1",
    slug: "carpinteria",
    name: "Carpinteria",
    suggested_lead_price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
  },
  photo_urls: ["https://cdn.test/a.jpg"],
  created_at: new Date(Date.now() - 3 * 3600_000).toISOString(),
  remaining_slots: 2,
  distance_km: 12.4,
  masked_phone: "*********44",
  masked_email: "a****@example.com",
  already_purchased: false,
  price: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
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

  it("omits distance when it is unknown", () => {
    renderWithIntl(<LeadCard lead={{ ...LEAD, distance_km: null }} />);
    expect(screen.queryByText(/km/)).toBeNull();
  });
});
