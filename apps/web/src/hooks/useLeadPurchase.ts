"use client";

/** Compra del contacto de una solicitud. */

import { useLocale } from "next-intl";
import { useCallback, useState } from "react";

import { useApiError } from "@/hooks/useApiError";
import { path } from "@/i18n/routing";
import { paymentService } from "@/services/payment.service";
import type { Locale } from "@/types/api";

export interface LeadPurchaseState {
  start: (leadId: string) => Promise<void>;
  pending: boolean;
  error: string | null;
  reset: () => void;
}

export interface LeadPurchaseOptions {
  /**
   * El saldo cubrio el contacto y ya esta desbloqueado. Quien muestra la solicitud lo
   * recarga ahi mismo: el profesional ve el contacto donde lo compro, sin recargar la
   * pagina (antes se iba a "Mis contactos" y una carrera de la sesion lo mandaba al
   * perfil).
   */
  onUnlocked?: (purchaseId: string) => void;
}

export function useLeadPurchase({ onUnlocked }: LeadPurchaseOptions = {}): LeadPurchaseState {
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
        if (result.checkout_url === null) {
          // Pagada con saldo: ya esta desbloqueada. `pending` sigue activo hasta que el
          // contacto reemplaza al boton, para que no haya un segundo click.
          if (onUnlocked) {
            onUnlocked(result.purchase_id);
          } else {
            window.location.assign(
              path(locale, "projects", `/${leadId}?purchase=${result.purchase_id}&status=success`),
            );
          }
          return;
        }
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
    [locale, translateError, onUnlocked],
  );

  return {
    start,
    pending,
    error,
    reset: useCallback(() => setError(null), []),
  };
}
