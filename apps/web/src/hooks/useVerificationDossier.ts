"use client";

/**
 * Expediente de alta y decision del admin (aprobar o rechazar). Lo comparten la cola
 * de validacion y el directorio de usuarios: `onDecided` refresca la lista que lo abrio.
 */

import { useLocale } from "next-intl";
import { useCallback, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { Locale, Rejection, VerificationDossier } from "@/types/api";

export interface VerificationDossierState {
  dossier: VerificationDossier | null;
  deciding: boolean;
  error: string | null;
  lastRejection: Rejection | null;
  open: (professionalId: string) => Promise<void>;
  close: () => void;
  approve: () => Promise<void>;
  reject: (reason: string) => Promise<void>;
}

export function useVerificationDossier(
  onDecided: () => Promise<void> | void,
): VerificationDossierState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [dossier, setDossier] = useState<VerificationDossier | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRejection, setLastRejection] = useState<Rejection | null>(null);

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
        await onDecided();
      } catch (caught) {
        // Un fallo de la pasarela al rechazar no guarda nada: se puede reintentar.
        setError(translateError(caught));
      } finally {
        setDeciding(false);
      }
    },
    [onDecided, translateError],
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

  const close = useCallback(() => setDossier(null), []);

  return { dossier, deciding, error, lastRejection, open, close, approve, reject };
}
