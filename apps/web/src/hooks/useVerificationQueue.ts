"use client";

/** Cola de validacion de altas (F02): pendientes, expediente y decision del admin. */

import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { AdminProfessional, Locale, Rejection, VerificationDossier } from "@/types/api";

export interface VerificationQueueState {
  queue: AdminProfessional[];
  dossier: VerificationDossier | null;
  loading: boolean;
  deciding: boolean;
  error: string | null;
  lastRejection: Rejection | null;
  open: (professionalId: string) => Promise<void>;
  close: () => void;
  approve: () => Promise<void>;
  reject: (reason: string) => Promise<void>;
}

export function useVerificationQueue(): VerificationQueueState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [queue, setQueue] = useState<AdminProfessional[]>([]);
  const [dossier, setDossier] = useState<VerificationDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRejection, setLastRejection] = useState<Rejection | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setQueue((await adminService.professionals("", locale, "pending")).items);
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [locale, translateError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const open = useCallback(
    async (professionalId: string) => {
      setError(null);
      setLastRejection(null);
      try {
        // Las URLs de descarga caducan en minutos: se piden al abrir, no antes.
        setDossier(await adminService.verificationDossier(professionalId, locale));
      } catch (caught) {
        setError(translateError(caught));
      }
    },
    [locale, translateError],
  );

  const decide = useCallback(
    async (action: () => Promise<unknown>) => {
      setDeciding(true);
      setError(null);
      try {
        await action();
        setDossier(null);
        await reload();
      } catch (caught) {
        // Un fallo de la pasarela al rechazar no guarda nada: se puede reintentar.
        setError(translateError(caught));
      } finally {
        setDeciding(false);
      }
    },
    [reload, translateError],
  );

  const approve = useCallback(async () => {
    const id = dossier?.professional.id;
    if (!id) return;
    await decide(() => adminService.approveProfessional(id, locale));
  }, [dossier, decide, locale]);

  const reject = useCallback(
    async (reason: string) => {
      const id = dossier?.professional.id;
      if (!id) return;
      await decide(async () => {
        setLastRejection(await adminService.rejectProfessional(id, reason, locale));
      });
    },
    [dossier, decide, locale],
  );

  return {
    queue,
    dossier,
    loading,
    deciding,
    error,
    lastRejection,
    open,
    close: () => setDossier(null),
    approve,
    reject,
  };
}
