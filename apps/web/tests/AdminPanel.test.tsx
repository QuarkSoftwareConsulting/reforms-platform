import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const metrics = {
  leads_total: 4,
  leads_published: 3,
  leads_exhausted: 1,
  leads_disabled: 0,
  leads_organic: 2,
  leads_admin: 2,
  professionals_total: 3,
  paid_purchases: 2,
  paid_leads: 2,
  coverage_rate: 0.5,
  liquidity: 0.5,
  revenue_by_currency: { EUR: { amount_cents: 1000, currency: "EUR", formatted: "10,00 €" } },
};

const lead = {
  id: "lead-admin-1",
  title: "Reparar persiana",
  description: "La persiana se atasca cada manana y necesita una reparacion completa.",
  city: "Madrid",
  province: "Madrid",
  postal_code_prefix: "28",
  category: {
    id: "cat-1",
    slug: "persianas",
    name: "Persianas",
    suggested_lead_price: { amount_cents: 500, currency: "EUR", formatted: "5,00 €" },
  },
  photo_urls: [],
  created_at: "2026-03-01T12:00:00Z",
  status: "published" as const,
  source: "admin" as const,
  purchases_count: 0,
  max_purchases: 3,
  remaining_slots: 3,
  price: { amount_cents: 500, currency: "EUR", formatted: "5,00 €" },
  client_name: "Ana Lopez",
};

vi.mock("@/services/admin.service", () => ({
  adminService: {
    metrics: vi.fn().mockResolvedValue(metrics),
    leads: vi.fn().mockResolvedValue({ items: [lead], total: 1, limit: 20, offset: 0 }),
    professionals: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 }),
    subscriptionPrice: vi.fn().mockResolvedValue({
      amount: { amount_cents: 1800, currency: "EUR", formatted: "18.00 €" },
      updated_at: null,
      is_default: true,
      configured: true,
    }),
    setSubscriptionPrice: vi.fn(),
    createLead: vi.fn(),
    disableLead: vi.fn(),
    republishLead: vi.fn(),
    setLeadPrice: vi.fn(),
    setCategoryPrice: vi.fn(),
    purchases: vi.fn(),
    reviewPurchase: vi.fn(),
  },
}));

vi.mock("@/services/leads.service", () => ({
  leadsService: { categories: vi.fn().mockResolvedValue([lead.category]) },
}));

const { AdminPanel } = await import("@/components/features/AdminPanel");
const { renderWithIntl, messages } = await import("./render");
const { adminService } = await import("@/services/admin.service");
const { ApiError } = await import("@/services/api");

describe("AdminPanel", () => {
  it("never reads accidental client fields from an admin lead", async () => {
    const { container } = renderWithIntl(<AdminPanel />);

    await waitFor(() => expect(screen.getByText("Reparar persiana")).toBeDefined());

    expect(screen.getAllByText(messages.admin.status.published)).toHaveLength(2);
    expect(container.innerHTML).not.toContain("Ana Lopez");
  });

  async function submitManualLead(acceptedAt: string): Promise<HTMLElement> {
    const { container } = renderWithIntl(<AdminPanel />);
    await waitFor(() => expect(container.querySelector("form")).not.toBeNull());
    const input = container.querySelector<HTMLInputElement>('input[name="accepted_at"]');
    fireEvent.change(input as HTMLInputElement, { target: { value: acceptedAt } });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    return container;
  }

  it("shows the specific reason when the backend rejects the manual lead", async () => {
    vi.mocked(adminService.createLead).mockRejectedValueOnce(
      new ApiError(422, {
        code: "CONSENT_DATE_IN_FUTURE",
        message: "La fecha del consentimiento no puede estar en el futuro",
        details: null,
      }),
    );

    await submitManualLead("2026-03-01T10:00");

    expect(await screen.findByText(messages.errors.CONSENT_DATE_IN_FUTURE)).toBeDefined();
    expect(screen.queryByText(messages.errors.VALIDATION_ERROR)).toBeNull();
  });

  it("confirms a created lead instead of reporting a connection error", async () => {
    vi.mocked(adminService.createLead).mockResolvedValueOnce({ id: "new-lead" } as never);

    const container = await submitManualLead("2026-03-01T10:00");

    expect(await screen.findByText(messages.admin.saved)).toBeDefined();
    expect(container.innerHTML).not.toContain(messages.errors.network);
  });

  it("asks for a valid acceptance date instead of failing silently", async () => {
    vi.mocked(adminService.createLead).mockClear();

    await submitManualLead("");

    expect(await screen.findByText(messages.admin.manual.invalidDate)).toBeDefined();
    expect(adminService.createLead).not.toHaveBeenCalled();
  });
});
