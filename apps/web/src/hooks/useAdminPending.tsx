"use client";

/**
 * Altas pendientes de validar: el contador de la pestana "Profesionales".
 *
 * Vive en un contexto del layout del admin para que la cola, al aprobar o rechazar,
 * actualice el numero sin otra peticion: `report` recibe el total que ella ya pide.
 */

import { useLocale } from "next-intl";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { adminService } from "@/services/admin.service";
import type { Locale } from "@/types/api";

interface AdminPendingState {
  count: number | null;
  report: (count: number) => void;
}

const AdminPendingContext = createContext<AdminPendingState | null>(null);

// Fuera del layout (p. ej. en un test de la cola) no hay contador que actualizar.
const NO_PROVIDER: AdminPendingState = { count: null, report: () => undefined };

export function AdminPendingProvider({ children }: { children: ReactNode }) {
  const locale = useLocale() as Locale;
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminService
      .professionals("", locale, "pending")
      .then((page) => {
        if (!cancelled) setCount(page.total);
      })
      // El contador es orientativo: si falla, la pestana se queda sin numero.
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const value = useMemo(() => ({ count, report: setCount }), [count]);
  return <AdminPendingContext.Provider value={value}>{children}</AdminPendingContext.Provider>;
}

export function useAdminPending(): AdminPendingState {
  return useContext(AdminPendingContext) ?? NO_PROVIDER;
}
