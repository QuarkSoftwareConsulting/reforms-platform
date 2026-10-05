"use client";

/**
 * Contexto de autenticacion.
 *
 * Envuelve Firebase Auth y conecta el proveedor de token del cliente HTTP, de
 * forma que ningun otro modulo necesita saber que la identidad viene de Firebase.
 */

import {
  createUserWithEmailAndPassword,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  type User as FirebaseUser,
} from "firebase/auth";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { firebaseAuth, googleProvider, isFirebaseConfigured } from "@/lib/firebase";
import { setTokenProvider } from "@/services/api";
import { professionalService } from "@/services/professional.service";
import type { Locale, Me } from "@/types/api";

export interface AuthState {
  /** `undefined` mientras Firebase resuelve la sesion inicial. */
  firebaseUser: FirebaseUser | null | undefined;
  /** Perfil del backend (cuenta + perfil profesional). */
  me: Me | null;
  loading: boolean;
  isAuthenticated: boolean;
  hasProfile: boolean;
  configured: boolean;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  /**
   * Recarga el perfil. Solo marca `loading` (y `AuthGate` desmonta la pagina) la primera
   * vez para cada usuario: refrescar una sesion ya cargada nunca la desmonta, se pase o
   * no `silent`. Asi ningun refresco puede provocar un bucle de desmontar y volver a
   * pedir (paso con la mensualidad: `/me` y `/me/account` sin fin).
   */
  refreshMe: (options?: { silent?: boolean }) => Promise<Me | null>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
  locale,
}: {
  children: ReactNode;
  locale: Locale;
}): ReactNode {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null | undefined>(
    isFirebaseConfigured ? undefined : null,
  );
  const [me, setMe] = useState<Me | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  // Usuario de Firebase cuyo `me` ya se resolvio (con o sin perfil). Hasta entonces la
  // sesion sigue "cargando": Firebase restaura al usuario un render antes de que
  // empiece la peticion de `me`, y en ese render `AuthGate` veia "sin perfil" y
  // mandaba a /perfil a un profesional que si lo tiene (tras comprar un contacto o
  // volver de Stripe, que recargan la pagina).
  const [profileResolvedFor, setProfileResolvedFor] = useState<string | null>(null);
  const currentUser = useRef<FirebaseUser | null>(null);
  // Lo mismo que `profileResolvedFor`, legible dentro de `refreshMe` sin recrearlo.
  const resolvedUid = useRef<string | null>(null);

  // El cliente HTTP pide el token justo antes de cada peticion en vez de recibir
  // una copia: asi nunca envia uno caducado.
  useEffect(() => {
    setTokenProvider(async (forceRefresh = false) => {
      const user = currentUser.current;
      if (!user) return null;
      return user.getIdToken(forceRefresh);
    });
  }, []);

  useEffect(() => {
    if (!isFirebaseConfigured) return;
    // `onIdTokenChanged` (y no `onAuthStateChanged`) para enterarnos tambien de las
    // renovaciones de token, no solo de los inicios y cierres de sesion.
    return onIdTokenChanged(firebaseAuth(), (user) => {
      currentUser.current = user;
      setFirebaseUser(user);
      if (!user) {
        // Sin sesion se olvida lo cargado: si vuelve a entrar el mismo usuario, su
        // perfil se carga de nuevo con `loading` (si no, `AuthGate` lo veria "sin
        // perfil" y lo mandaria a /perfil).
        setMe(null);
        resolvedUid.current = null;
        setProfileResolvedFor(null);
      }
    });
  }, []);

  const refreshMe = useCallback(async ({ silent = false } = {}): Promise<Me | null> => {
    const user = currentUser.current;
    if (!user) {
      setMe(null);
      return null;
    }
    const alreadyLoaded = resolvedUid.current === user.uid;
    const blocking = !silent && !alreadyLoaded;
    if (blocking) setProfileLoading(true);
    // Si la sesion cambio mientras llegaba la respuesta (salio, o entro otro), esa
    // respuesta ya no es de nadie: aplicarla dejaria el perfil de A tras su logout o
    // lo marcaria como "cargado" y, al volver a entrar, `AuthGate` no esperaria a su `me`.
    const stillCurrent = () => currentUser.current?.uid === user.uid;
    try {
      const profile = await professionalService.me(locale);
      if (stillCurrent()) setMe(profile);
      return profile;
    } catch {
      // Un fallo aqui no debe tumbar la app. En la primera carga la UI lo trata como
      // "sin perfil"; en un refresco se conserva el perfil que ya habia: borrarlo
      // mandaria a /perfil a un profesional por un fallo de red pasajero.
      if (stillCurrent() && !alreadyLoaded) setMe(null);
      return null;
    } finally {
      if (stillCurrent()) {
        resolvedUid.current = user.uid;
        setProfileResolvedFor(user.uid);
      }
      if (blocking) setProfileLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    if (firebaseUser) {
      void refreshMe();
    }
  }, [firebaseUser, refreshMe]);

  const value = useMemo<AuthState>(
    () => ({
      firebaseUser,
      me,
      loading:
        firebaseUser === undefined ||
        profileLoading ||
        (firebaseUser !== null && profileResolvedFor !== firebaseUser.uid),
      isAuthenticated: Boolean(firebaseUser),
      hasProfile: Boolean(me?.professional),
      configured: isFirebaseConfigured,
      async signInWithEmail(email, password) {
        await signInWithEmailAndPassword(firebaseAuth(), email, password);
      },
      async signUpWithEmail(email, password) {
        await createUserWithEmailAndPassword(firebaseAuth(), email, password);
      },
      async signInWithGoogle() {
        await signInWithPopup(firebaseAuth(), googleProvider);
      },
      async logout() {
        await signOut(firebaseAuth());
        setMe(null);
      },
      refreshMe,
    }),
    [firebaseUser, me, profileLoading, profileResolvedFor, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  }
  return context;
}
