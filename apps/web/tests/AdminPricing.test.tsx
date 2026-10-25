import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AdminPricing } from "@/components/features/AdminPricing";
import { adminService } from "@/services/admin.service";

import { messages, renderWithIntl } from "./render";

vi.mock("@/services/admin.service", () => ({
  adminService: { subscriptionPrice: vi.fn(), setSubscriptionPrice: vi.fn() },
}));

describe("AdminPricing", () => {
  it("sends the category price to the catalog instead of editing it here", async () => {
    vi.mocked(adminService.subscriptionPrice).mockResolvedValue({
      amount: { amount_cents: 1800, currency: "EUR", formatted: "" },
      configured: true,
      updated_at: null,
    });
    renderWithIntl(<AdminPricing />);

    const link = await screen.findByRole("link", { name: messages.admin.categoryPricing.link });
    expect(link.getAttribute("href")).toBe("/es/admin/catalogo");
    // El precio sugerido se edita en un solo sitio: el catalogo.
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});
