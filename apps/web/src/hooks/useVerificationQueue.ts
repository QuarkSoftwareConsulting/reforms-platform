"use client";

/** Cola de validacion de altas (F02): pendientes, expediente y decision del admin. */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { useVerificationDossier, type VerificationDossierState } from "@/hooks/useVerificationDossier";
import { adminService } from "@/services/admin.service";
import type { AdminProfessional, Locale } from "@/types/api";

export interface VerificationQueueState extends VerificationDossierState {
  queue: AdminProfessional[];
  loading: boolean;
}

export function useVerificationQueue(): VerificationQueueState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [queue, setQueue] = useState<AdminProfessional[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setQueue((await adminService.professionals("", locale, "pending")).items);
    } catch (caught) {
      setLoadError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [locale, translateError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const dossier = useVerificationDossier(reload);

  return { ...dossier, error: dossier.error ?? loadError, queue, loading };
}
