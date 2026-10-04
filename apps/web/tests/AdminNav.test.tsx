/** Pestanas del backoffice: la activa sale de la URL y "Profesionales" cuenta pendientes. */

import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

let pathname = "/es/admin";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

const professionals = vi.fn();
vi.mock("@/services/admin.service", () => ({ adminService: { professionals } }));

const { AdminNav } = await import("@/components/features/AdminNav");
const { AdminPendingProvider } = await import("@/hooks/useAdminPending");
const { renderWithIntl, messages } = await import("./render");

function renderNav() {
  return renderWithIntl(
    <AdminPendingProvider>
      <AdminNav />
    </AdminPendingProvider>,
  );
}

function tab(name: string): HTMLElement {
  return screen.getByRole("link", { name: new RegExp(`^${name}`) });
}

describe("AdminNav", () => {
  it("marks only the overview as current at the admin root", () => {
    professionals.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    pathname = "/es/admin";
    renderNav();

    expect(tab(messages.admin.nav.overview).getAttribute("aria-current")).toBe("page");
    expect(tab(messages.admin.nav.leads).getAttribute("aria-current")).toBeNull();
  });

  it("marks the section of a subroute and not the overview", () => {
    professionals.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    pathname = "/es/admin/solicitudes";
    renderNav();

    expect(tab(messages.admin.nav.leads).getAttribute("aria-current")).toBe("page");
    expect(tab(messages.admin.nav.overview).getAttribute("aria-current")).toBeNull();
    expect(tab(messages.admin.nav.leads).getAttribute("href")).toBe("/es/admin/solicitudes");
  });

  it("shows how many sign-ups are waiting for review", async () => {
    professionals.mockResolvedValue({ items: [], total: 3, limit: 20, offset: 0 });
    pathname = "/es/admin";
    renderNav();

    await waitFor(() =>
      expect(tab(messages.admin.nav.professionals).textContent).toContain("3"),
    );
    expect(professionals).toHaveBeenCalledWith("", "es", "pending");
  });
});
