import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AdminDashboard } from "@/components/features/AdminDashboard";
import { adminService } from "@/services/admin.service";

import { messages, renderWithIntl } from "./render";

vi.mock("@/services/admin.service", () => ({
  adminService: { metrics: vi.fn(), metricsTimeseries: vi.fn() },
}));

const EUR = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: "" });

describe("AdminDashboard", () => {
  it("labels the totals as all-time and explains lead liquidity", async () => {
    vi.mocked(adminService.metrics).mockResolvedValue({
      leads_total: 3,
      leads_published: 2,
      leads_exhausted: 0,
      leads_disabled: 1,
      leads_organic: 3,
      leads_admin: 0,
      professionals_total: 2,
      paid_purchases: 2,
      paid_leads: 1,
      coverage_rate: 1 / 3,
      liquidity: 2 / 3,
      revenue_by_currency: { EUR: EUR(4600) },
      active_accounts: 1,
      topup_revenue_by_currency: {},
    });
    vi.mocked(adminService.metricsTimeseries).mockResolvedValue({
      start: "2026-11-18",
      end: "2026-11-24",
      timezone: "Europe/Madrid",
      points: [],
    });
    renderWithIntl(<AdminDashboard />);

    // El periodo solo filtra las graficas: los totales deben decir que son historicos.
    expect(
      await screen.findByRole("heading", { name: messages.admin.dashboard.totalsTitle }),
    ).toBeTruthy();
    expect(screen.getByText(messages.admin.dashboard.totalsHint)).toBeTruthy();
    expect(screen.getByText("0.67")).toBeTruthy();
    expect(screen.getByText(messages.admin.metrics.liquidityHint)).toBeTruthy();
  });
});
