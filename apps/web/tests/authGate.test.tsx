/**
 * Carga de la sesion en una pagina protegida.
 *
 * El fallo que cubre: tras una recarga completa (comprar un contacto, volver de
 * Stripe) Firebase restaura al usuario un render antes de que empiece la peticion de
 * `me`. En ese render la sesion parecia cargada y "sin perfil", y `AuthGate` mandaba
 * a /perfil a un profesional que si lo tiene.
 */

import { act, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
const meMock = vi.fn();
let emitUser: (user: unknown) => void = () => undefined;

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
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

const { AuthProvider } = await import("@/hooks/useAuth");
const { AuthGate } = await import("@/components/features/AuthGate");
const { renderWithIntl } = await import("./render");

const USER = { uid: "firebase-uid-1", getIdToken: async () => "token" };

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function renderGate() {
  return renderWithIntl(
    <AuthProvider locale="es">
      <AuthGate>
        <p>contenido protegido</p>
      </AuthGate>
    </AuthProvider>,
  );
}

describe("AuthGate al recargar la pagina", () => {
  beforeEach(() => {
    replace.mockReset();
    meMock.mockReset();
  });

  it("does not send a professional with a profile to /perfil while `me` loads", async () => {
    const me = deferred<unknown>();
    meMock.mockReturnValue(me.promise);
    renderGate();

    act(() => emitUser(USER));
    // Firebase ya tiene al usuario y `me` aun no responde: es el render que fallaba.
    expect(replace).not.toHaveBeenCalled();

    await act(async () => {
      me.resolve({ professional: { id: "p1" } });
    });

    expect(await screen.findByText("contenido protegido")).toBeDefined();
    expect(replace).not.toHaveBeenCalled();
  });

  it("still sends a user without a profile to /perfil once `me` says so", async () => {
    meMock.mockResolvedValue({ professional: null });
    renderGate();

    await act(async () => {
      emitUser(USER);
    });

    expect(replace).toHaveBeenCalledWith("/es/perfil");
  });

  it("sends a visitor without a session to the login", async () => {
    renderGate();

    act(() => emitUser(null));

    expect(replace).toHaveBeenCalledWith("/es/login");
    expect(meMock).not.toHaveBeenCalled();
  });
});
