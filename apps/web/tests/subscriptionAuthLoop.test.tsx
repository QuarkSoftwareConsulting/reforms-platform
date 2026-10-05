/**
 * Vuelta del checkout de la mensualidad con la sesion real (AuthProvider + AuthGate).
 *
 * El fallo que cubre (5 de octubre, en dev): con la cuenta ya activa, el panel
 * refrescaba la sesion sin `silent`; `AuthGate` lo desmontaba mientras cargaba, al
 * volver montaba uno nuevo que habia olvidado que ya refresco, y vuelta a empezar:
 * `/me` y `/me/account` en bucle. Los tests del panel con `useAuth` simulado no lo
 * podian ver.
 */

import { act, screen } from "@testing-library/react";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const meMock = vi.fn();
const accountMock = vi.fn();
let emitUser: (user: unknown) => void = () => undefined;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("status=success"),
}));
vi.mock("@/lib/firebase", () => ({
  isFirebaseConfigured: true,
  firebaseAuth: () => ({}),
  googleProvider: {},
}));
vi.mock("firebase/auth", () => ({
  onIdTokenChanged: (_auth: unknown, callback: (user: unknown) => void) => {
    emitUser = callback;
    return () => undefined;
  },
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("@/services/professional.service", () => ({
  professionalService: { me: (...args: unknown[]) => meMock(...args) },
}));
vi.mock("@/services/subscription.service", () => ({
  subscriptionService: {
    account: (...args: unknown[]) => accountMock(...args),
    startCheckout: vi.fn(),
    openPortal: vi.fn(),
  },
}));

const { AuthProvider } = await import("@/hooks/useAuth");
const { AuthGate } = await import("@/components/features/AuthGate");
const { SubscriptionPanel } = await import("@/components/features/SubscriptionPanel");
const { renderWithIntl, messages } = await import("./render");

const EUR = (cents: number) => ({
  amount_cents: cents,
  currency: "EUR",
  formatted: `${cents / 100} €`,
});

describe("SubscriptionPanel con la sesion real", () => {
  beforeEach(() => {
    meMock.mockReset();
    accountMock.mockReset();
    meMock.mockResolvedValue({ professional: { id: "p1" }, account: null });
    accountMock.mockResolvedValue({
      status: "active",
      is_active: true,
      balance: EUR(1000),
      topup_amount: EUR(1000),
      current_period_end: null,
      can_manage_billing: true,
      entries: [],
      debt: null,
    });
  });

  it("refreshes the session once after activation, without a reload loop", async () => {
    renderWithIntl(
      <AuthProvider locale="es">
        <AuthGate>
          <Suspense>
            <SubscriptionPanel />
          </Suspense>
        </AuthGate>
      </AuthProvider>,
    );
    await act(async () => {
      emitUser({ uid: "firebase-uid-1", getIdToken: async () => "token" });
    });
    expect(await screen.findByText(messages.subscription.status.active)).toBeDefined();

    // Margen de sobra para que un bucle se note: cada vuelta son dos peticiones.
    for (let i = 0; i < 20; i += 1) {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }

    // Una carga de la sesion al entrar y un refresco tras ver la cuenta activa.
    expect(meMock).toHaveBeenCalledTimes(2);
    expect(accountMock).toHaveBeenCalledTimes(1);
  });
});
