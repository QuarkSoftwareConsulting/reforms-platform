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
  refreshMe: () => Promise<Me | null>;
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
  const currentUser = useRef<FirebaseUser | null>(null);

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
      if (!user) setMe(null);
    });
  }, []);

  const refreshMe = useCallback(async (): Promise<Me | null> => {
    if (!currentUser.current) {
      setMe(null);
      return null;
    }
    setProfileLoading(true);
    try {
      const profile = await professionalService.me(locale);
      setMe(profile);
      return profile;
    } catch {
      // Un fallo aqui no debe tumbar la app: la UI lo tratara como "sin perfil".
      setMe(null);
      return null;
    } finally {
      setProfileLoading(false);
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
      loading: firebaseUser === undefined || profileLoading,
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
    [firebaseUser, me, profileLoading, refreshMe],
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
