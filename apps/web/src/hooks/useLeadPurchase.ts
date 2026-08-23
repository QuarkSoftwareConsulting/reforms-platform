"use client";

/** Compra del contacto de una solicitud. */

import { useLocale } from "next-intl";
import { useCallback, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { paymentService } from "@/services/payment.service";
import type { Locale } from "@/types/api";

export interface LeadPurchaseState {
  start: (leadId: string) => Promise<void>;
  pending: boolean;
  error: string | null;
  reset: () => void;
}

export function useLeadPurchase(): LeadPurchaseState {
  const locale = useLocale() as Locale;
  const translateError = useApiError();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async (leadId: string) => {
      setPending(true);
      setError(null);
      try {
        const result = await paymentService.startPurchase(leadId, locale);
        // Navegacion completa (no router.push): el checkout esta en otro dominio.
        window.location.assign(result.checkout_url);
      } catch (caught) {
        setError(translateError(caught));
        // `pending` solo se libera en el fallo: si la redireccion funciona, la
        // pagina se esta yendo y volver a habilitar el boton invitaria a un doble
        // click que crearia una segunda reserva.
        setPending(false);
      }
    },
    [locale, translateError],
  );

  return {
    start,
    pending,
    error,
    reset: useCallback(() => setError(null), []),
  };
}
