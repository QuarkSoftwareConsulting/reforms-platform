"use client";

/** Metricas acumuladas y actividad diaria del dashboard del admin. */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { lastDaysRange } from "@/helpers/date";
import { useApiError } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { AdminMetrics, Locale, MetricsTimeseries } from "@/types/api";

export const RANGE_PRESETS = [7, 30, 90] as const;
export type RangePreset = (typeof RANGE_PRESETS)[number];

export interface AdminDashboardState {
  metrics: AdminMetrics | null;
  series: MetricsTimeseries | null;
  days: RangePreset;
  setDays: (days: RangePreset) => void;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useAdminDashboard(): AdminDashboardState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [series, setSeries] = useState<MetricsTimeseries | null>(null);
  const [days, setDays] = useState<RangePreset>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Solo cuenta la respuesta de la ultima peticion: al cambiar de rango rapido (30 -> 7 ->
  // 90), una respuesta lenta anterior pintaria otro periodo con el chip de 90 marcado.
  const latest = useRef(0);

  const reload = useCallback(async () => {
    const request = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const { from, to } = lastDaysRange(days);
      const [nextMetrics, nextSeries] = await Promise.all([
        adminService.metrics(locale),
        adminService.metricsTimeseries(from, to, locale),
      ]);
      if (request !== latest.current) return;
      setMetrics(nextMetrics);
      setSeries(nextSeries);
    } catch (caught) {
      if (request === latest.current) setError(translateError(caught));
    } finally {
      if (request === latest.current) setLoading(false);
    }
  }, [days, locale, translateError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { metrics, series, days, setDays, loading, error, reload };
}
