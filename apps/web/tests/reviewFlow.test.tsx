/**
 * Envio del alta a revision (F02): guardar es el unico paso del profesional y, si el
 * alta queda completa, se pide confirmar en un dialogo antes de enviarla.
 *
 * Lo que se vigila: el dialogo solo sale con el alta completa y sin enviar, confirmar
 * envia una vez, y el refresco tras guardar no desmonta la pagina (parpadeo).
 */

import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Professional, Verification } from "@/types/api";

import messages from "../messages/es.json";

const upsertProfile = vi.fn();
const submitForReview = vi.fn();
const refreshMe = vi.fn();
let currentProfessional: Professional | null = null;

vi.mock("@/services/professional.service", () => ({
  professionalService: {
    upsertProfile: (...args: unknown[]) => upsertProfile(...args),
    submitForReview: (...args: unknown[]) => submitForReview(...args),
  },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ me: { professional: currentProfessional }, refreshMe }),
}));

const { useProfessionalProfile } = await import("@/hooks/useProfessionalProfile");
const { ReviewConfirmDialog } = await import("@/components/features/profile/ReviewConfirmDialog");
const { renderWithIntl } = await import("./render");

const t = messages.profile.reviewDialog;

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

function professional(overrides: Partial<Verification> = {}): Professional {
  return {
    id: "p1",
    business_name: "Reformas Lopez",
    phone: "612345678",
    postal_code: "28001",
    city: null,
    province: null,
    service_radius_km: 25,
    categories: [{ id: "3f6d4f4e-6a0f-4a43-9d57-5a0c1d6f3a10" }],
    services: [],
    professional_type: "self_employed",
    legal_name: "Ana Lopez",
    tax_id: "12345678Z",
    address: "Calle Mayor 1",
    profile_photo: null,
    logo: null,
    work_photos: [],
    documents: [],
    verification: verification(overrides),
  } as unknown as Professional;
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="es" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("useProfessionalProfile: confirmacion del envio", () => {
  beforeEach(() => {
    upsertProfile.mockReset();
    submitForReview.mockReset();
    refreshMe.mockReset();
    refreshMe.mockResolvedValue(null);
    currentProfessional = professional();
  });

  it("asks for confirmation after saving a complete registration", async () => {
    upsertProfile.mockResolvedValue(professional());
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.reviewPrompt).toBe(true);
    expect(submitForReview).not.toHaveBeenCalled();
  });

  it("does not ask while something is still missing", async () => {
    upsertProfile.mockResolvedValue(professional({ missing: ["document_tax_registration"] }));
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.reviewPrompt).toBe(false);
  });

  it("does not ask again once the registration was sent", async () => {
    upsertProfile.mockResolvedValue(professional({ status: "pending" }));
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.reviewPrompt).toBe(false);
  });

  it("sends once on confirm and closes the prompt", async () => {
    upsertProfile.mockResolvedValue(professional());
    submitForReview.mockResolvedValue(professional({ status: "pending" }));
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });
    await act(async () => {
      await result.current.confirmReview();
    });

    expect(submitForReview).toHaveBeenCalledOnce();
    expect(result.current.reviewPrompt).toBe(false);
  });

  it("dismissing sends nothing", async () => {
    upsertProfile.mockResolvedValue(professional());
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });
    act(() => result.current.dismissReview());

    expect(result.current.reviewPrompt).toBe(false);
    expect(submitForReview).not.toHaveBeenCalled();
  });

  it("refreshes the session silently so the page is not unmounted", async () => {
    upsertProfile.mockResolvedValue(professional());
    const { result } = renderHook(() => useProfessionalProfile(), { wrapper });

    await act(async () => {
      await result.current.save();
    });

    expect(refreshMe).toHaveBeenCalledWith({ silent: true });
  });
});

describe("ReviewConfirmDialog", () => {
  it("renders nothing while closed", () => {
    renderWithIntl(
      <ReviewConfirmDialog open={false} submitting={false} onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("warns that the data gets locked and lets the user confirm", async () => {
    const onConfirm = vi.fn();
    renderWithIntl(
      <ReviewConfirmDialog open submitting={false} onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("dialog", { name: t.title })).toBeDefined();
    expect(screen.getByText(t.warning)).toBeDefined();
    await userEvent.setup().click(screen.getByRole("button", { name: t.confirm }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("closes with the cancel button and with Escape", async () => {
    const onCancel = vi.fn();
    renderWithIntl(
      <ReviewConfirmDialog open submitting={false} onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: t.cancel }));
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("cannot be dismissed while sending", async () => {
    const onCancel = vi.fn();
    renderWithIntl(
      <ReviewConfirmDialog open submitting onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    await userEvent.setup().keyboard("{Escape}");
    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: t.cancel })).toHaveProperty("disabled", true);
  });
});
