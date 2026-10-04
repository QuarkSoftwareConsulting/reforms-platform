/**
 * Vuelta del checkout de la mensualidad antes de que llegue el webhook.
 *
 * El fallo que cubren (4 de octubre): el profesional pago, volvio y, sin el webhook
 * confirmado, el panel le ofrecia otra vez "Activar mensualidad". Pulsarlo abria una
 * segunda suscripcion en Stripe: un segundo cobro mensual.
 */

import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Account } from "@/types/api";

const accountMock = vi.fn();
const startCheckout = vi.fn();
const refreshMe = vi.fn();
let search = new URLSearchParams();

vi.mock("@/services/subscription.service", () => ({
  subscriptionService: {
    account: (...args: unknown[]) => accountMock(...args),
    startCheckout: (...args: unknown[]) => startCheckout(...args),
    openPortal: vi.fn(),
  },
}));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ refreshMe }) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));

const { SubscriptionPanel } = await import("@/components/features/SubscriptionPanel");
const { ApiError } = await import("@/services/api");
const { renderWithIntl, messages } = await import("./render");

const t = messages.subscription;
const EUR = (cents: number) => ({ amount_cents: cents, currency: "EUR", formatted: `${cents / 100} €` });

function account(overrides: Partial<Account> = {}): Account {
  return {
    status: "none",
    is_active: false,
    balance: EUR(0),
    topup_amount: EUR(1000),
    current_period_end: null,
    can_manage_billing: true,
    entries: [],
    debt: null,
    ...overrides,
  };
}

const activateButton = () => screen.queryByRole("button", { name: /Activar mensualidad/ });

/** Avanza el sondeo del panel: cada vuelta espera 3 s y vuelve a pedir la cuenta. */
async function advancePolls(times: number): Promise<void> {
  for (let i = 0; i < times; i += 1) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
  }
}

describe("SubscriptionPanel: vuelta del checkout", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    accountMock.mockReset();
    startCheckout.mockReset();
    refreshMe.mockReset();
    search = new URLSearchParams();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not offer to pay again while the payment is being confirmed", async () => {
    search = new URLSearchParams("status=success");
    accountMock.mockResolvedValue(account());
    renderWithIntl(<SubscriptionPanel />);

    expect(await screen.findByText(t.confirming)).toBeDefined();
    expect(activateButton()).toBeNull();
  });

  it("keeps waiting instead of offering to pay when confirmation is slow", async () => {
    search = new URLSearchParams("status=success");
    accountMock.mockResolvedValue(account());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithIntl(<SubscriptionPanel />);
    await screen.findByText(t.confirming);

    await advancePolls(10);

    expect(await screen.findByText(t.confirmationDelayed)).toBeDefined();
    expect(activateButton()).toBeNull();
    const calls = accountMock.mock.calls.length;
    await user.click(screen.getByRole("button", { name: t.checkAgain }));
    expect(accountMock.mock.calls.length).toBe(calls + 1);
  });

  it("shows the active account as soon as the webhook lands", async () => {
    search = new URLSearchParams("status=success");
    accountMock
      .mockResolvedValueOnce(account())
      .mockResolvedValue(account({ status: "active", is_active: true, balance: EUR(1000) }));
    renderWithIntl(<SubscriptionPanel />);
    await screen.findByText(t.confirming);

    await advancePolls(1);

    expect(await screen.findByText(t.status.active)).toBeDefined();
    expect(screen.queryByText(t.confirming)).toBeNull();
    expect(refreshMe).toHaveBeenCalledTimes(1);
  });

  it("switches to waiting when Stripe already has the subscription", async () => {
    accountMock.mockResolvedValue(account());
    startCheckout.mockRejectedValue(
      new ApiError(409, { code: "SUBSCRIPTION_ALREADY_EXISTS", message: "x", details: null }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithIntl(<SubscriptionPanel />);

    const activate = await screen.findByRole("button", { name: /Activar mensualidad/ });
    await user.click(activate);

    expect(await screen.findByText(t.confirming)).toBeDefined();
    expect(activateButton()).toBeNull();
  });

  it("still offers to subscribe after a cancelled checkout", async () => {
    search = new URLSearchParams("status=cancelled");
    accountMock.mockResolvedValue(account());
    renderWithIntl(<SubscriptionPanel />);

    expect(await screen.findByText(t.checkoutCancelled)).toBeDefined();
    expect(activateButton()).not.toBeNull();
  });
});
