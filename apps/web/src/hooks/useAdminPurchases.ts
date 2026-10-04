"use client";

/** Listado global de compras: quien compro que, cuando y por cuanto. */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { AdminPurchase, Locale, PurchaseStatus } from "@/types/api";

export const PURCHASES_PAGE_SIZE = 20;

export interface AdminPurchasesFilters {
  status?: PurchaseStatus;
  /** `YYYY-MM-DD`, inclusivo. */
  from?: string;
  /** `YYYY-MM-DD`, inclusivo. */
  to?: string;
}

export interface AdminPurchasesState {
  items: AdminPurchase[];
  total: number;
  page: number;
  pages: number;
  filters: AdminPurchasesFilters;
  loading: boolean;
  error: string | null;
  setFilters: (filters: AdminPurchasesFilters) => void;
  setPage: (page: number) => void;
}

export function useAdminPurchases(): AdminPurchasesState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [items, setItems] = useState<AdminPurchase[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filters, setFiltersState] = useState<AdminPurchasesFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Solo cuenta la respuesta de la ultima peticion: al cambiar de filtro rapido, una
  // respuesta lenta anterior no debe pisar la lista nueva.
  const latest = useRef(0);

  const load = useCallback(async () => {
    const request = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const result = await adminService.allPurchases(
        {
          status: filters.status,
          from: filters.from,
          to: filters.to,
          limit: PURCHASES_PAGE_SIZE,
          offset: page * PURCHASES_PAGE_SIZE,
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
  }, [filters, locale, page, translateError]);

  useEffect(() => {
    void load();
  }, [load]);

  const setFilters = useCallback((next: AdminPurchasesFilters) => {
    setFiltersState(next);
    setPage(0);
  }, []);

  return {
    items,
    total,
    page,
    pages: Math.max(1, Math.ceil(total / PURCHASES_PAGE_SIZE)),
    filters,
    loading,
    error,
    setFilters,
    setPage,
  };
}
