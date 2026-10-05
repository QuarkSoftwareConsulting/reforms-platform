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

const { AuthProvider, useAuth } = await import("@/hooks/useAuth");
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

let auth: ReturnType<typeof useAuth> | null = null;

/** Expone la sesion al test, como haria cualquier componente que la use. */
function Probe() {
  auth = useAuth();
  return null;
}

function renderGate() {
  return renderWithIntl(
    <AuthProvider locale="es">
      <Probe />
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

  describe("refrescar una sesion ya cargada", () => {
    async function loaded(): Promise<void> {
      meMock.mockResolvedValue({ professional: { id: "p1" } });
      renderGate();
      await act(async () => {
        emitUser(USER);
      });
      await screen.findByText("contenido protegido");
    }

    it("never unmounts the page, even without `silent`", async () => {
      // Sin esto, un refresco sin `silent` desmontaba la pagina y quien lo pidio al
      // montarse lo volvia a pedir: el bucle `/me` + `/me/account` de la mensualidad.
      await loaded();
      const me = deferred<unknown>();
      meMock.mockReturnValue(me.promise);

      act(() => {
        void auth?.refreshMe();
      });

      expect(screen.queryByText("contenido protegido")).not.toBeNull();
      await act(async () => {
        me.resolve({ professional: { id: "p1" } });
      });
      expect(screen.queryByText("contenido protegido")).not.toBeNull();
    });

    it("keeps the profile if a refresh fails, instead of sending to /perfil", async () => {
      await loaded();
      meMock.mockRejectedValue(new TypeError("Failed to fetch"));

      await act(async () => {
        await auth?.refreshMe({ silent: true });
      });

      expect(auth?.hasProfile).toBe(true);
      expect(replace).not.toHaveBeenCalled();
    });

    it("loads the profile again when the same user signs back in", async () => {
      await loaded();
      act(() => emitUser(null));
      replace.mockReset();
      const me = deferred<unknown>();
      meMock.mockReturnValue(me.promise);

      act(() => emitUser(USER));

      // Mientras llega su `me`, no es "sin perfil".
      expect(replace).not.toHaveBeenCalled();
      await act(async () => {
        me.resolve({ professional: { id: "p1" } });
      });
      expect(await screen.findByText("contenido protegido")).toBeDefined();
      expect(replace).not.toHaveBeenCalled();
    });
  });

  it("ignores the answer of a request from a session that already ended", async () => {
    // Revision: A entra, sale antes de que llegue su `me` y esa peticion falla tarde.
    // Su `finally` volvia a marcar a A como cargado, y al volver a entrar A no
    // esperaba a su perfil: `AuthGate` lo veia "sin perfil" y lo mandaba a /perfil.
    const first = deferred<unknown>();
    meMock.mockReturnValueOnce(first.promise);
    renderGate();
    act(() => emitUser(USER));
    act(() => emitUser(null));
    await act(async () => {
      first.resolve(Promise.reject(new TypeError("sin token")));
    });

    const second = deferred<unknown>();
    meMock.mockReturnValueOnce(second.promise);
    act(() => emitUser(USER));
    await act(async () => {
      second.resolve({ professional: { id: "p1" } });
    });

    expect(await screen.findByText("contenido protegido")).toBeDefined();
    // Al salir si va al login (es lo correcto); al perfil, nunca.
    expect(replace).not.toHaveBeenCalledWith("/es/perfil");
  });
});
