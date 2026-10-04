/**
 * Roles, compras globales y dashboard del admin.
 *
 * Lo que se vigila: el cambio de rol pide confirmacion y deja nota, un admin no ve
 * el boton de cambiarse a si mismo, los errores llegan traducidos por `code`, el
 * listado de compras no pinta datos del cliente y el dashboard pide los dias de Madrid.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatDay, lastDaysRange } from "@/helpers/date";
import { ApiError } from "@/services/api";
import type { AdminPurchase, AdminUser, MetricsTimeseries } from "@/types/api";

const users = vi.fn();
const setUserRole = vi.fn();
const allPurchases = vi.fn();
const metrics = vi.fn();
const metricsTimeseries = vi.fn();

vi.mock("@/services/admin.service", () => ({
  adminService: {
    users: (...args: unknown[]) => users(...args),
    setUserRole: (...args: unknown[]) => setUserRole(...args),
    allPurchases: (...args: unknown[]) => allPurchases(...args),
    metrics: (...args: unknown[]) => metrics(...args),
    metricsTimeseries: (...args: unknown[]) => metricsTimeseries(...args),
    verificationDossier: vi.fn(),
    approveProfessional: vi.fn(),
    rejectProfessional: vi.fn(),
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ me: { user_id: "admin-1", role: "admin" } }),
}));

const { AdminUsers } = await import("@/components/features/AdminUsers");
const { AdminPurchases } = await import("@/components/features/AdminPurchases");
const { AdminDashboard } = await import("@/components/features/AdminDashboard");
const { renderWithIntl, messages } = await import("./render");

const tUsers = messages.admin.users;
const EUR = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: "" });

const admin: AdminUser = {
  id: "admin-1",
  email: "admin@example.com",
  display_name: null,
  role: "admin",
  created_at: "2026-09-01T10:00:00Z",
  professional: null,
};

const pro: AdminUser = {
  id: "pro-1",
  email: "pro@example.com",
  display_name: "Ana",
  role: "professional",
  created_at: "2026-09-02T10:00:00Z",
  professional: {
    id: "prof-1",
    business_name: "Reformas Sol",
    postal_code: "28001",
    city: "Madrid",
    province: "Madrid",
    service_radius_km: 20,
    categories: [],
    account: null,
    legal_name: null,
    verification_status: "pending",
    submitted_at: "2026-09-03T10:00:00Z",
  },
};

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function page<T>(items: T[]) {
  return { items, total: items.length, limit: 20, offset: 0 };
}

describe("AdminUsers", () => {
  beforeEach(() => {
    users.mockReset().mockResolvedValue(page([admin, pro]));
    setUserRole.mockReset();
  });

  it("promotes a professional after confirming, with the note", async () => {
    setUserRole.mockResolvedValue({ ...pro, role: "admin" });
    const user = userEvent.setup();
    renderWithIntl(<AdminUsers />);

    const row = (await screen.findByText("pro@example.com")).closest("li");
    expect(row).not.toBeNull();
    await user.click(within(row as HTMLElement).getByRole("button", { name: tUsers.makeAdmin }));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(tUsers.confirmPromote)).toBeDefined();
    await user.type(within(dialog).getByLabelText(new RegExp(escape(tUsers.noteLabel))), "soporte");
    await user.click(within(dialog).getByRole("button", { name: tUsers.confirm }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(setUserRole).toHaveBeenCalledWith("pro-1", "admin", "soporte", "es");
    expect(screen.getByText(tUsers.roleChanged)).toBeDefined();
    expect(within(row as HTMLElement).getByText(tUsers.roles.admin)).toBeDefined();
  });

  it("shows the professional's debt and lets the admin adjust the balance", async () => {
    const indebted: AdminUser = {
      ...pro,
      professional: pro.professional && {
        ...pro.professional,
        account: {
          status: "past_due",
          is_active: false,
          balance: EUR(0),
          current_period_end: null,
          debt: { amount_cents: 700, currency: "EUR", formatted: "7,00 €" },
        },
      },
    };
    users.mockResolvedValue(page([admin, indebted]));
    renderWithIntl(<AdminUsers />);

    const row = (await screen.findByText("pro@example.com")).closest("li") as HTMLElement;
    expect(within(row).getByText(new RegExp(`${messages.admin.debt} 7,00`))).toBeDefined();
    expect(within(row).getByText(messages.admin.adjustment.open)).toBeDefined();
    // Sin perfil profesional no hay saldo que ajustar.
    const adminRow = screen.getByText("admin@example.com").closest("li") as HTMLElement;
    expect(within(adminRow).queryByText(messages.admin.adjustment.open)).toBeNull();
  });

  it("does not offer changing your own role", async () => {
    renderWithIntl(<AdminUsers />);

    const row = (await screen.findByText("admin@example.com")).closest("li") as HTMLElement;
    expect(within(row).queryByRole("button", { name: tUsers.makeProfessional })).toBeNull();
  });

  it("shows the translated error and keeps the dialog open", async () => {
    setUserRole.mockRejectedValue(
      new ApiError(409, { code: "LAST_ADMIN", message: "raw backend message" }),
    );
    const user = userEvent.setup();
    renderWithIntl(<AdminUsers />);

    const row = (await screen.findByText("pro@example.com")).closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: tUsers.makeAdmin }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: tUsers.confirm }));

    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(messages.errors.LAST_ADMIN)).toBeDefined();
    expect(screen.queryByText("raw backend message")).toBeNull();
  });
});

describe("AdminUsers search", () => {
  it("waits for the user to stop typing and ignores a stale response", async () => {
    // La carga inicial (sin texto) responde DESPUES que la busqueda: no debe pisarla.
    let resolveInitial: (value: unknown) => void = () => undefined;
    users
      .mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => (resolveInitial = resolve)))
      .mockResolvedValue(page([pro]));
    const user = userEvent.setup();
    renderWithIntl(<AdminUsers />);

    await user.type(screen.getByLabelText(new RegExp(escape(tUsers.search))), "ana");
    expect(await screen.findByText("pro@example.com")).toBeDefined();
    resolveInitial(page([admin]));

    await waitFor(() => expect(screen.queryByText("admin@example.com")).toBeNull());
    expect(screen.getByText("pro@example.com")).toBeDefined();
    // Una peticion al cargar y otra con la palabra completa, no una por letra.
    expect(users.mock.calls.map(([filters]) => (filters as { query: string }).query)).toEqual([
      "",
      "ana",
    ]);
  });
});

describe("AdminPurchases", () => {
  it("lists who bought what without client data", async () => {
    const purchase = {
      purchase: {
        id: "pur-1",
        status: "paid",
        amount: EUR(500),
        credit_applied: EUR(500),
        created_at: "2026-09-10T10:00:00Z",
        paid_at: "2026-09-10T10:01:00Z",
        reserved_until: null,
      },
      professional: pro.professional,
      review_count: 0,
      lead: {
        id: "lead-1",
        title: "Reparar persiana",
        city: "Madrid",
        province: "Madrid",
        category: null,
        // Un campo que el API no manda: si llegara, no debe pintarse.
        client_phone: "+34611223344",
      },
    } as unknown as AdminPurchase;
    allPurchases.mockReset().mockResolvedValue(page([purchase]));

    const { container } = renderWithIntl(<AdminPurchases />);

    expect(await screen.findByText("Reparar persiana")).toBeDefined();
    expect(screen.getByText(/Reformas Sol/)).toBeDefined();
    expect(container.innerHTML).not.toContain("611223344");
  });
});

describe("AdminDashboard", () => {
  beforeEach(() => {
    metrics.mockReset().mockResolvedValue({
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
      revenue_by_currency: {},
      active_accounts: 1,
      topup_revenue_by_currency: {},
    });
    const series: MetricsTimeseries = {
      start: "2026-09-01",
      end: "2026-09-02",
      timezone: "Europe/Madrid",
      points: [
        {
          day: "2026-09-01",
          leads_created: 0,
          paid_purchases: 0,
          revenue_by_currency: {},
          topups: 0,
          topup_revenue_by_currency: {},
        },
        {
          day: "2026-09-02",
          leads_created: 7,
          paid_purchases: 2,
          revenue_by_currency: { EUR: EUR(1000) },
          topups: 1,
          topup_revenue_by_currency: { EUR: EUR(1800) },
        },
      ],
    };
    metricsTimeseries.mockReset().mockResolvedValue(series);
  });

  it("asks for the last 30 days and charts each measure separately", async () => {
    const user = userEvent.setup();
    renderWithIntl(<AdminDashboard />);

    const leadsChart = (
      await screen.findByText(messages.admin.dashboard.leadsChart)
    ).closest("figure") as HTMLElement;
    expect(within(leadsChart).getByRole("img", { name: /7$/ })).toBeDefined();
    const range = lastDaysRange(30);
    expect(metricsTimeseries).toHaveBeenCalledWith(range.from, range.to, "es");

    await user.click(
      screen.getByLabelText(messages.admin.dashboard.lastDays.replace("{days}", "7")),
    );
    await waitFor(() =>
      expect(metricsTimeseries).toHaveBeenLastCalledWith(
        lastDaysRange(7).from,
        lastDaysRange(7).to,
        "es",
      ),
    );
  });

  it("ignores a slow answer for a range the admin already left", async () => {
    const user = userEvent.setup();
    const base = (await metricsTimeseries()) as MetricsTimeseries;
    const withLeads = (count: number): MetricsTimeseries => ({
      ...base,
      points: base.points.map((point, index) =>
        index === 1 ? { ...point, leads_created: count } : point,
      ),
    });
    renderWithIntl(<AdminDashboard />);
    const chart = async () =>
      (await screen.findByText(messages.admin.dashboard.leadsChart)).closest(
        "figure",
      ) as HTMLElement;
    await within(await chart()).findByRole("img", { name: /7$/ });

    // La de 7 dias se queda colgada; la de 90 llega antes y la de 7 despues.
    let answerSevenDays: (value: MetricsTimeseries) => void = () => undefined;
    metricsTimeseries
      .mockImplementationOnce(
        () => new Promise((resolve) => (answerSevenDays = resolve)),
      )
      .mockResolvedValueOnce(withLeads(9));
    const preset = (days: number) =>
      screen.getByLabelText(messages.admin.dashboard.lastDays.replace("{days}", String(days)));
    await user.click(preset(7));
    await user.click(preset(90));
    await within(await chart()).findByRole("img", { name: /9$/ });

    answerSevenDays(withLeads(5));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(within(await chart()).queryByRole("img", { name: /5$/ })).toBeNull();
    expect(within(await chart()).getByRole("img", { name: /9$/ })).toBeDefined();
  });
});

describe("date range helpers", () => {
  it("counts days in Madrid, both ends included", () => {
    // 23:30 UTC del 31-ago son las 01:30 del 1-sep en Madrid (UTC+2 en verano).
    const now = Date.UTC(2026, 7, 31, 23, 30);
    expect(lastDaysRange(7, now)).toEqual({ from: "2026-08-26", to: "2026-09-01" });
  });

  it("formats a day without shifting it by the browser time zone", () => {
    expect(formatDay("2026-03-01", "es")).toBe("1 mar");
  });
});
