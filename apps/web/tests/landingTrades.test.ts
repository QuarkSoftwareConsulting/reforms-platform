import { describe, expect, it } from "vitest";

import { featuredTrades, toleratesApiOutage } from "@/helpers/landing";
import type { CatalogCategory } from "@/types/api";

const eur = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: "" });

function category(slug: string, cents: number, services: [string, boolean][]): CatalogCategory {
  return {
    id: `cat-${slug}`,
    slug,
    name: slug,
    suggested_lead_price: eur(cents),
    services: services.map(([service, featured]) => ({
      id: `svc-${service}`,
      slug: service,
      name: service.toUpperCase(),
      featured,
      landing_name: service.toUpperCase(),
    })),
  };
}

describe("featuredTrades", () => {
  it("keeps only featured services, in catalog order, with their category price", () => {
    const trades = featuredTrades([
      category("reformas", 900, [
        ["banos", true],
        ["cocinas", false],
      ]),
      category("obras-menores", 500, [["pintores", true]]),
    ]);

    expect(trades).toEqual([
      { serviceId: "svc-banos", name: "BANOS", categorySlug: "reformas", serviceSlug: "banos", price: eur(900) },
      {
        serviceId: "svc-pintores",
        name: "PINTORES",
        categorySlug: "obras-menores",
        serviceSlug: "pintores",
        price: eur(500),
      },
    ]);
  });

  it("shows nothing when nobody is featured", () => {
    expect(featuredTrades([category("reformas", 900, [["banos", false]])])).toEqual([]);
  });

  it("titles the card with the short landing name", () => {
    const [trade] = featuredTrades([
      {
        id: "cat-reformas",
        slug: "reformas",
        name: "Reformas",
        suggested_lead_price: eur(900),
        services: [
          {
            id: "svc-banos",
            slug: "reformas-banos",
            name: "Reformas de baños",
            featured: true,
            landing_name: "Baños",
          },
        ],
      },
    ]);
    expect(trade?.name).toBe("Baños");
  });
});

describe("toleratesApiOutage", () => {
  it("renders without the catalog only while building or in development", () => {
    expect(toleratesApiOutage("phase-production-build", "production")).toBe(true);
    expect(toleratesApiOutage(undefined, "development")).toBe(true);
  });

  it("lets a production regeneration fail so Next keeps the last good page", () => {
    expect(toleratesApiOutage(undefined, "production")).toBe(false);
    expect(toleratesApiOutage("phase-production-server", "production")).toBe(false);
  });
});
