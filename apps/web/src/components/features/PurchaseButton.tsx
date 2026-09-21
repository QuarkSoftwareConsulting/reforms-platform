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
    <div className="space-y-4 rounded-card border border-line bg-surface p-6">
      <div className="space-y-1">
        <p className="text-card-title font-semibold text-ink">{t("contactLocked")}</p>
        <p className="text-[14.5px] leading-[1.6] text-secondary">
          {t("contactLockedBody", { price, slots: detail.lead.remaining_slots })}
        </p>
      </div>

      {/* El precio del contacto se ve siempre antes de pagar. */}
      <p className="flex items-baseline justify-between gap-3 border-t border-divider pt-3.5">
        <span className="text-[11px] uppercase tracking-[0.7px] text-muted">
          {t("contactPrice")}
        </span>
        <span className="text-[19px] font-bold text-brand">{price}</span>
      </p>

      {reserved && minutesLeft > 0 && (
        <Alert tone="warning">{t("reservationPending", { minutes: minutesLeft })}</Alert>
      )}

      <Button
        type="button"
        variant="accent"
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
