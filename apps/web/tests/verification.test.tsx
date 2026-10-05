/**
 * Alta del profesional en el front (F02).
 *
 * Lo que se vigila: no se ofrece enviar un alta incompleta, el estado se ve en
 * "Solicitudes" mientras no se pueda comprar, y el admin no rechaza sin motivo.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/services/api";
import type { AdminProfessional, Verification, VerificationDossier } from "@/types/api";

const professionals = vi.fn();
const verificationDossier = vi.fn();
const approveProfessional = vi.fn();
const rejectProfessional = vi.fn();

vi.mock("@/services/admin.service", () => ({
  adminService: {
    professionals: (...args: unknown[]) => professionals(...args),
    verificationDossier: (...args: unknown[]) => verificationDossier(...args),
    approveProfessional: (...args: unknown[]) => approveProfessional(...args),
    rejectProfessional: (...args: unknown[]) => rejectProfessional(...args),
  },
}));

const { VerificationCard } = await import("@/components/features/profile/VerificationCard");
const { VerificationBanner } = await import("@/components/features/VerificationBanner");
const { AdminVerificationQueue } = await import("@/components/features/AdminVerificationQueue");
const { renderWithIntl, messages } = await import("./render");

const t = messages.profile.verification;

function verification(overrides: Partial<Verification> = {}): Verification {
  return {
    status: "incomplete",
    submitted_at: null,
    reviewed_at: null,
    rejection_reason: null,
    missing: [],
    ...overrides,
  };
}

describe("VerificationCard", () => {
  it("lists what is missing", () => {
    renderWithIntl(
      <VerificationCard
        verification={verification({ missing: ["tax_id", "document_tax_registration"] })}
      />,
    );
    expect(screen.getByText(t.missing.tax_id)).toBeDefined();
    expect(screen.getByText(t.missing.document_tax_registration)).toBeDefined();
  });

  it("has no submit button: sending is confirmed after saving, not from here", () => {
    renderWithIntl(<VerificationCard verification={verification()} />);
    expect(screen.getByText(t.readyBody)).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows the rejection reason", () => {
    renderWithIntl(
      <VerificationCard
        verification={verification({ status: "rejected", rejection_reason: "Ilegible" })}
      />,
    );
    expect(screen.getByText(t.rejectedTitle)).toBeDefined();
    expect(screen.getByText(/Ilegible/)).toBeDefined();
  });
});

describe("VerificationBanner", () => {
  it("is silent once approved", () => {
    const { container } = renderWithIntl(
      <VerificationBanner verification={verification({ status: "approved" })} />,
    );
    expect(container.textContent).toBe("");
  });

  it("tells a pending professional they can browse but not buy yet", () => {
    renderWithIntl(<VerificationBanner verification={verification({ status: "pending" })} />);
    expect(screen.getByText(t.bannerPending)).toBeDefined();
  });

  it("links an incomplete professional to the registration", () => {
    renderWithIntl(<VerificationBanner verification={verification()} />);
    expect(screen.getByRole("link", { name: t.bannerCta })).toBeDefined();
  });
});

describe("AdminVerificationQueue", () => {
  const tAdmin = messages.admin.verification;
  const queued: AdminProfessional = {
    id: "pro-1",
    business_name: "Reformas Lopez",
    legal_name: "Ana Lopez Garcia",
    postal_code: "28001",
    city: "Madrid",
    province: "Madrid",
    service_radius_km: 25,
    categories: [],
    account: null,
    verification_status: "pending",
    submitted_at: "2026-09-28T10:00:00Z",
  };
  const dossier = {
    professional: {
      id: "pro-1",
      business_name: "Reformas Lopez",
      legal_name: "Ana Lopez Garcia",
      tax_id: "12345678Z",
      professional_type: "self_employed",
      address: "Calle Mayor 1",
      phone: "611223344",
      postal_code: "28001",
      verification: {
        status: "pending",
        submitted_at: "2026-09-28T09:00:00Z",
        reviewed_at: null,
        rejection_reason: null,
        missing: [],
      },
    },
    email: "ana@example.com",
    documents: [
      {
        id: "doc-1",
        kind: "tax_registration",
        filename: "036.pdf",
        uploaded_at: "2026-09-28T09:00:00Z",
        download_url: "https://private.test/036.pdf?signature=x",
      },
    ],
    events: [],
  } as unknown as VerificationDossier;

  beforeEach(() => {
    professionals.mockReset().mockResolvedValue({ items: [queued], total: 1, limit: 20, offset: 0 });
    verificationDossier.mockReset().mockResolvedValue(dossier);
    approveProfessional.mockReset().mockResolvedValue({});
    rejectProfessional.mockReset().mockResolvedValue({
      professional: {},
      refunded: { amount_cents: 1800, currency: "EUR", formatted: "18.00 €" },
      subscription_canceled: true,
    });
  });

  it("asks only for pending registrations", async () => {
    renderWithIntl(<AdminVerificationQueue />);
    expect(await screen.findByText("Ana Lopez Garcia")).toBeDefined();
    expect(professionals).toHaveBeenCalledWith("", "es", "pending");
  });

  it("opens the dossier with the signed document link and approves", async () => {
    const user = userEvent.setup();
    renderWithIntl(<AdminVerificationQueue />);
    await user.click(await screen.findByRole("button", { name: tAdmin.review }));

    const link = await screen.findByRole("link", { name: "036.pdf" });
    expect(link.getAttribute("href")).toBe("https://private.test/036.pdf?signature=x");

    await user.click(screen.getByRole("button", { name: tAdmin.approve }));
    await waitFor(() => expect(approveProfessional).toHaveBeenCalledWith("pro-1", "es"));
  });

  it("needs a reason to reject and reports the refund", async () => {
    const user = userEvent.setup();
    renderWithIntl(<AdminVerificationQueue />);
    await user.click(await screen.findByRole("button", { name: tAdmin.review }));
    const reject = await screen.findByRole("button", { name: tAdmin.reject });
    expect(reject).toHaveProperty("disabled", true);

    await user.type(screen.getByLabelText(new RegExp(tAdmin.reasonLabel)), "Documento ilegible");
    await user.click(reject);

    await waitFor(() =>
      expect(rejectProfessional).toHaveBeenCalledWith("pro-1", "Documento ilegible", "es"),
    );
    expect(await screen.findByText(/Se reembolsaron 18,00/)).toBeDefined();
  });

  it("clears a failed reload's error once a later reload succeeds", async () => {
    const page = (items: AdminProfessional[]) => ({ items, total: items.length, limit: 20, offset: 0 });
    professionals
      .mockReset()
      .mockResolvedValueOnce(page([queued]))
      .mockRejectedValueOnce(new ApiError(503, { code: "PAYMENT_GATEWAY_ERROR", message: "x" }))
      .mockResolvedValue(page([]));
    const user = userEvent.setup();
    renderWithIntl(<AdminVerificationQueue />);

    // Aprobar recarga la cola: esa recarga falla y la lista anterior sigue visible.
    await user.click(await screen.findByRole("button", { name: tAdmin.review }));
    await user.click(await screen.findByRole("button", { name: tAdmin.approve }));
    expect(await screen.findByText(messages.errors.PAYMENT_GATEWAY_ERROR)).toBeDefined();

    // La siguiente recarga funciona: el error viejo no debe quedarse.
    await user.click(await screen.findByRole("button", { name: tAdmin.review }));
    await user.click(await screen.findByRole("button", { name: tAdmin.approve }));
    expect(await screen.findByText(tAdmin.empty)).toBeDefined();
    expect(screen.queryByText(messages.errors.PAYMENT_GATEWAY_ERROR)).toBeNull();
  });
});
