/**
 * Inicializacion del SDK de Firebase en el navegador.
 *
 * Es el unico modulo que importa `firebase/*`. El resto de la app habla con
 * `useAuth`, de modo que cambiar de proveedor de identidad se queda aqui.
 */

import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  connectAuthEmulator,
  getAuth,
  GoogleAuthProvider,
  type Auth,
} from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "",
};

const EMULATOR_HOST = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;

let emulatorConnected = false;

function firebaseApp(): FirebaseApp {
  return getApps().length > 0 ? getApp() : initializeApp(config);
}

/** Instancia de Auth, conectada al emulador si esta configurado. */
export function firebaseAuth(): Auth {
  const auth = getAuth(firebaseApp());
  if (EMULATOR_HOST && !emulatorConnected) {
    // `connectAuthEmulator` falla si se llama dos veces sobre la misma instancia.
    connectAuthEmulator(auth, EMULATOR_HOST, { disableWarnings: true });
    emulatorConnected = true;
  }
  return auth;
}

export const googleProvider = new GoogleAuthProvider();

export const isFirebaseConfigured = Boolean(config.apiKey && config.projectId);
