"use client";

import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { formatMoney } from "@/helpers/currency";
import { minutesUntil } from "@/helpers/date";
import { useLeadPurchase } from "@/hooks/useLeadPurchase";
import type { AppLocale } from "@/i18n/routing";
import type { LeadDetail } from "@/types/api";

/**
 * Bloque de desbloqueo del contacto.
 *
 * Tres estados posibles: contacto ya desbloqueado, reserva en curso pendiente de
 * pago, o bloqueado. La reserva en curso se muestra aparte porque el profesional
 * ya consumio una plaza y necesita saber que tiene un plazo para pagar.
 */
export function PurchaseButton({ detail }: { detail: LeadDetail }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("lead");
  const purchase = useLeadPurchase();

  if (detail.is_unlocked) {
    return null;
  }

  const reserved = detail.purchase?.status === "reserved";
  const minutesLeft = minutesUntil(detail.purchase?.reserved_until ?? null);
  const price = formatMoney(detail.lead.price, locale);

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="space-y-1">
        <p className="font-semibold text-slate-900">{t("contactLocked")}</p>
        <p className="text-sm text-slate-600">
          {t("contactLockedBody", { price, slots: detail.lead.remaining_slots })}
        </p>
      </div>

      {reserved && minutesLeft > 0 && (
        <Alert tone="warning">{t("reservationPending", { minutes: minutesLeft })}</Alert>
      )}

      <Button
        type="button"
        size="lg"
        fullWidth
        loading={purchase.pending}
        disabled={detail.lead.remaining_slots === 0}
        onClick={() => void purchase.start(detail.lead.id)}
      >
        {purchase.pending
          ? t("unlocking")
          : reserved
            ? t("resumePayment")
            : t("unlock", { price })}
      </Button>

      {purchase.error && <Alert tone="error">{purchase.error}</Alert>}
    </div>
  );
}
