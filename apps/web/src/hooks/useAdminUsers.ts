"use client";

/**
 * Directorio de usuarios del admin: busqueda, cambio de rol y expediente de alta.
 * El rol vive en la BD, asi que el cambio surte efecto en la siguiente peticion del
 * usuario; aqui solo se sustituye su fila por la que devuelve el API.
 */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import type { VerificationStatus } from "@/helpers/professionalOptions";
import { useApiError } from "@/hooks/useApiError";
import { useVerificationDossier, type VerificationDossierState } from "@/hooks/useVerificationDossier";
import { adminService } from "@/services/admin.service";
import type { AdminUser, Locale, UserRole } from "@/types/api";

export const USERS_PAGE_SIZE = 20;
/** Espera tras la ultima tecla antes de buscar: una peticion por palabra, no por letra. */
export const SEARCH_DEBOUNCE_MS = 300;

export interface AdminUsersFilters {
  query: string;
  role?: UserRole;
  verificationStatus?: VerificationStatus;
}

export interface AdminUsersState {
  items: AdminUser[];
  total: number;
  page: number;
  pages: number;
  filters: AdminUsersFilters;
  loading: boolean;
  error: string | null;
  changingRole: boolean;
  setFilters: (filters: AdminUsersFilters) => void;
  setPage: (page: number) => void;
  /** Devuelve `true` si se guardo; el error queda en `roleError`. */
  changeRole: (userId: string, role: UserRole, note: string) => Promise<boolean>;
  roleError: string | null;
  clearRoleError: () => void;
  dossier: VerificationDossierState;
}

export function useAdminUsers(): AdminUsersState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filters, setFiltersState] = useState<AdminUsersFilters>({ query: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [changingRole, setChangingRole] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  // Solo cuenta la respuesta de la ultima peticion: una lenta anterior no pisa la nueva.
  const latest = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => setSearchQuery(filters.query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [filters.query]);

  const { role, verificationStatus } = filters;
  const load = useCallback(async () => {
    const request = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const result = await adminService.users(
        {
          query: searchQuery,
          role,
          verificationStatus,
          limit: USERS_PAGE_SIZE,
          offset: page * USERS_PAGE_SIZE,
        },
        locale,
      );
      if (request !== latest.current) return;
      setItems(result.items);
      setTotal(result.total);
    } catch (caught) {
      if (request === latest.current) setError(translateError(caught));
    } finally {
      if (request === latest.current) setLoading(false);
    }
  }, [searchQuery, role, verificationStatus, locale, page, translateError]);

  useEffect(() => {
    void load();
  }, [load]);

  const setFilters = useCallback((next: AdminUsersFilters) => {
    setFiltersState(next);
    setPage(0);
  }, []);

  const changeRole = useCallback(
    async (userId: string, role: UserRole, note: string) => {
      setChangingRole(true);
      setRoleError(null);
      try {
        const updated = await adminService.setUserRole(userId, role, note.trim() || null, locale);
        setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        return true;
      } catch (caught) {
        setRoleError(translateError(caught));
        return false;
      } finally {
        setChangingRole(false);
      }
    },
    [locale, translateError],
  );

  const dossier = useVerificationDossier(load);

  return {
    items,
    total,
    page,
    pages: Math.max(1, Math.ceil(total / USERS_PAGE_SIZE)),
    filters,
    loading,
    error,
    changingRole,
    setFilters,
    setPage,
    changeRole,
    roleError,
    clearRoleError: () => setRoleError(null),
    dossier,
  };
}
