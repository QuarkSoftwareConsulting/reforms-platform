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
    id: "6f1c2a8e-3d5b-4c7a-9e2f-1a2b3c4d5e6f",
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

const { AdminLeads } = await import("@/components/features/AdminLeads");
const { renderWithIntl, messages } = await import("./render");
const { adminService } = await import("@/services/admin.service");
const { ApiError } = await import("@/services/api");

describe("AdminLeads", () => {
  it("never reads accidental client fields from an admin lead", async () => {
    const { container } = renderWithIntl(<AdminLeads />);

    await waitFor(() => expect(screen.getByText("Reparar persiana")).toBeDefined());

    expect(screen.getAllByText(messages.admin.status.published)).toHaveLength(2);
    expect(container.innerHTML).not.toContain("Ana Lopez");
  });

  it("keeps the manual lead form folded until it is asked for", async () => {
    const { container } = renderWithIntl(<AdminLeads />);
    await waitFor(() => expect(screen.getByText("Reparar persiana")).toBeDefined());

    expect(container.querySelector("form")).toBeNull();
    const toggle = screen.getByRole("button", { name: messages.admin.leads.showManual });
    fireEvent.click(toggle);

    expect(container.querySelector("form")).not.toBeNull();
    expect(screen.getByRole("button", { name: messages.admin.leads.hideManual })).toBeDefined();
  });

  it("opens the purchases of a lead in a dialog", async () => {
    vi.mocked(adminService.purchases).mockResolvedValueOnce([]);
    renderWithIntl(<AdminLeads />);
    await waitFor(() => expect(screen.getByText("Reparar persiana")).toBeDefined());

    fireEvent.click(screen.getByRole("button", { name: messages.admin.leads.purchases }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain(messages.admin.purchases.empty);
  });

  const MANUAL_LEAD: Record<string, string> = {
    category_id: lead.category.id,
    title: "Cambiar la cerradura",
    description: "La cerradura de la puerta principal se ha roto y no cierra bien.",
    postal_code: "28001",
    client_name: "Ana Lopez",
    client_phone: "612345678",
    channel: "Llamada",
    policy_version: "2026-09-v2",
    accepted_at: "2026-03-01T10:00",
  };

  /** Rellena el alta manual (con `overrides` encima) y la envia. */
  async function submitManualLead(overrides: Record<string, string> = {}): Promise<HTMLElement> {
    const { container } = renderWithIntl(<AdminLeads />);
    await waitFor(() =>
      expect(screen.getAllByRole("option", { name: lead.category.name })).not.toHaveLength(0),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.admin.leads.showManual }));
    const form = container.querySelector("form") as HTMLFormElement;
    for (const [name, value] of Object.entries({ ...MANUAL_LEAD, ...overrides })) {
      const control = form.querySelector(`[name="${name}"]`) as HTMLInputElement;
      fireEvent.change(control, { target: { value } });
    }
    fireEvent.submit(form);
    return container;
  }

  it("shows the specific reason on its field when the backend rejects the manual lead", async () => {
    vi.mocked(adminService.createLead).mockRejectedValueOnce(
      new ApiError(422, {
        code: "CONSENT_DATE_IN_FUTURE",
        message: "La fecha del consentimiento no puede estar en el futuro",
        details: null,
      }),
    );

    const container = await submitManualLead();

    expect(await screen.findByText(messages.errors.CONSENT_DATE_IN_FUTURE)).toBeDefined();
    expect(screen.queryByText(messages.errors.VALIDATION_ERROR)).toBeNull();
    const acceptedAt = container.querySelector('[name="accepted_at"]');
    expect(acceptedAt?.getAttribute("aria-invalid")).toBe("true");
  });

  it("confirms a created lead next to the button instead of a connection error", async () => {
    vi.mocked(adminService.createLead).mockResolvedValueOnce({ id: "new-lead" } as never);

    const container = await submitManualLead();

    const created = messages.admin.manual.created.replace("{title}", MANUAL_LEAD.title!);
    expect(await screen.findByText(created)).toBeDefined();
    expect(container.innerHTML).not.toContain(messages.errors.network);
  });

  it("asks for the acceptance date instead of failing silently", async () => {
    vi.mocked(adminService.createLead).mockClear();

    await submitManualLead({ accepted_at: "" });

    expect(await screen.findByText(messages.validation.acceptedAtRequired)).toBeDefined();
    expect(adminService.createLead).not.toHaveBeenCalled();
  });

  it("lists the missing fields next to the button and moves focus there", async () => {
    vi.mocked(adminService.createLead).mockClear();

    await submitManualLead({ client_phone: "", channel: "" });

    const title = await screen.findByText(/^Revisa 2 campos para continuar$/);
    const summary = title.closest("[tabindex]");
    await waitFor(() => expect(document.activeElement).toBe(summary));
    expect(summary?.textContent).toContain(messages.admin.manual.phone);
    expect(summary?.textContent).toContain(messages.admin.manual.channel);
    expect(adminService.createLead).not.toHaveBeenCalled();
  });
});
