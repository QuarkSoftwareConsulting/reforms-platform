"use client";

/** Estado y carga del explorador de solicitudes. */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { leadsService } from "@/services/leads.service";
import type { LeadList, Locale } from "@/types/api";

const PAGE_SIZE = 12;

export interface ProjectFilterState {
  data: LeadList | null;
  loading: boolean;
  error: string | null;
  categoryIds: string[];
  radiusKm: number | null;
  page: number;
  totalPages: number;
  setCategoryIds: (ids: string[]) => void;
  setRadiusKm: (km: number | null) => void;
  setPage: (page: number) => void;
  reload: () => void;
}

export function useProjectFilter(initialRadiusKm: number | null = null): ProjectFilterState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();

  const [categoryIds, setCategoryIdsState] = useState<string[]>([]);
  const [radiusKm, setRadiusKmState] = useState<number | null>(initialRadiusKm);
  const [page, setPage] = useState(0);
  const [data, setData] = useState<LeadList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Cada cambio de filtro cancela la peticion anterior: sin esto, una respuesta
    // lenta de un filtro ya descartado podria sobrescribir la actual.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    leadsService
      .list(
        {
          categoryIds: categoryIds.length > 0 ? categoryIds : undefined,
          radiusKm: radiusKm ?? undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        },
        locale,
      )
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(translateError(caught));
        setLoading(false);
      });

    return () => controller.abort();
  }, [categoryIds, radiusKm, page, locale, translateError, reloadToken]);

  const setCategoryIds = useCallback((ids: string[]) => {
    setCategoryIdsState(ids);
    setPage(0); // un filtro nuevo invalida la pagina actual
  }, []);

  const setRadiusKm = useCallback((km: number | null) => {
    setRadiusKmState(km);
    setPage(0);
  }, []);

  return {
    data,
    loading,
    error,
    categoryIds,
    radiusKm,
    page,
    totalPages: data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1,
    setCategoryIds,
    setRadiusKm,
    setPage,
    reload: useCallback(() => setReloadToken((token) => token + 1), []),
  };
}

export { PAGE_SIZE };
