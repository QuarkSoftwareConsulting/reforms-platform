/**
 * Tests del hook de compra.
 *
 * Lo critico: un doble click no puede crear dos reservas, porque cada reserva
 * consume una de las plazas limitadas del lead.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../messages/es.json";

const startPurchase = vi.fn();

vi.mock("@/services/payment.service", () => ({
  paymentService: {
    startPurchase: (...args: unknown[]) => startPurchase(...args),
  },
}));

const { useLeadPurchase } = await import("@/hooks/useLeadPurchase");
const { ApiError } = await import("@/services/api");

const assign = vi.fn();

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="es" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("useLeadPurchase", () => {
  beforeEach(() => {
    startPurchase.mockReset();
    assign.mockReset();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { assign, href: "http://localhost/" },
    });
  });

  it("redirects to the checkout URL returned by the API", async () => {
    startPurchase.mockResolvedValue({
      purchase_id: "purchase-1",
      checkout_url: "https://checkout.stripe.test/cs_123",
      amount: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
      expires_at: null,
    });

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    expect(startPurchase).toHaveBeenCalledWith("lead-1", "es");
    expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/cs_123");
  });

  it("stays pending after a successful redirect so a second click cannot double-book", async () => {
    startPurchase.mockResolvedValue({
      purchase_id: "purchase-1",
      checkout_url: "https://checkout.stripe.test/cs_123",
      amount: { amount_cents: 500, currency: "EUR", formatted: "5.00 €" },
      expires_at: null,
    });

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    expect(result.current.pending).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("translates the cap-reached error into the user's language", async () => {
    startPurchase.mockRejectedValue(
      new ApiError(409, { code: "LEAD_CAP_REACHED", message: "cap" }),
    );

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    await waitFor(() => expect(result.current.error).toBe(messages.errors.LEAD_CAP_REACHED));
    expect(assign).not.toHaveBeenCalled();
  });

  it("re-enables the button after a failure so the user can retry", async () => {
    startPurchase.mockRejectedValue(
      new ApiError(500, { code: "INTERNAL_ERROR", message: "boom" }),
    );

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    await waitFor(() => expect(result.current.pending).toBe(false));
    expect(result.current.error).toBe(messages.errors.INTERNAL_ERROR);
  });

  it("falls back to a generic message for unknown error codes", async () => {
    startPurchase.mockRejectedValue(
      new ApiError(400, { code: "SOMETHING_NEW", message: "raw backend text" }),
    );

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    // No se filtra el texto crudo del backend al usuario.
    await waitFor(() => expect(result.current.error).toBe(messages.errors.generic));
  });

  it("reports a network failure distinctly", async () => {
    startPurchase.mockRejectedValue(new TypeError("Failed to fetch"));

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });

    await waitFor(() => expect(result.current.error).toBe(messages.errors.network));
  });

  it("clears the error on reset", async () => {
    startPurchase.mockRejectedValue(
      new ApiError(409, { code: "LEAD_ALREADY_PURCHASED", message: "dup" }),
    );

    const { result } = renderHook(() => useLeadPurchase(), { wrapper });
    await act(async () => {
      await result.current.start("lead-1");
    });
    await waitFor(() => expect(result.current.error).not.toBeNull());

    act(() => result.current.reset());
    expect(result.current.error).toBeNull();
  });
});
