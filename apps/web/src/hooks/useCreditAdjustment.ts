"use client";

/** Ajuste manual del saldo de un profesional desde el panel de admin. */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useState } from "react";

import { parseAdjustment, type AdjustmentDirection } from "@/helpers/credit";
import { useApiError } from "@/hooks/useApiError";
import { adminService } from "@/services/admin.service";
import type { AdminAccount, Locale } from "@/types/api";

export interface CreditAdjustmentState {
  pending: boolean;
  error: string | null;
  /** Devuelve la cuenta ajustada, o null si no se envio (validacion o error del API). */
  submit: (direction: AdjustmentDirection, amount: string, note: string) => Promise<AdminAccount | null>;
}

export function useCreditAdjustment(professionalId: string): CreditAdjustmentState {
  const locale = useLocale() as Locale;
  const tValidation = useTranslations("validation");
  const translateError = useApiError();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(
    async (direction: AdjustmentDirection, amount: string, note: string) => {
      const draft = parseAdjustment(direction, amount, note);
      if (!draft.ok) {
        setError(tValidation(draft.error));
        return null;
      }
      setPending(true);
      setError(null);
      try {
        return await adminService.adjustCredit(professionalId, draft.amountCents, draft.note, locale);
      } catch (caught) {
        // Un cargo mayor que el saldo llega como INSUFFICIENT_CREDIT: no deja deuda.
        setError(translateError(caught));
        return null;
      } finally {
        setPending(false);
      }
    },
    [professionalId, locale, tValidation, translateError],
  );

  return { pending, error, submit };
}
