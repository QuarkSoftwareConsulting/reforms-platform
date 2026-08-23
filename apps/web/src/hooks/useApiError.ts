"use client";

/** Traduce errores del API y de Firebase al idioma del usuario. */

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import { ApiError } from "@/services/api";

export interface ErrorTranslator {
  (error: unknown): string;
}

function firebaseErrorCode(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as { code: unknown }).code;
    if (typeof code === "string" && code.startsWith("auth/")) return code;
  }
  return null;
}

/**
 * Devuelve una funcion que convierte cualquier error en un mensaje mostrable.
 *
 * Los codigos del backend (`LEAD_CAP_REACHED`) y los de Firebase
 * (`auth/invalid-credential`) son claves de traduccion; lo que no reconocemos cae
 * en un mensaje genérico en vez de filtrar detalles tecnicos al usuario.
 */
export function useApiError(): ErrorTranslator {
  const t = useTranslations("errors");

  return useCallback(
    (error: unknown): string => {
      const authCode = firebaseErrorCode(error);
      if (authCode) {
        return t.has(authCode) ? t(authCode) : t("generic");
      }
      if (error instanceof ApiError) {
        return t.has(error.code) ? t(error.code) : t("generic");
      }
      if (error instanceof TypeError) {
        // fetch lanza TypeError cuando no hay red o el CORS falla.
        return t("network");
      }
      return t("generic");
    },
    [t],
  );
}
