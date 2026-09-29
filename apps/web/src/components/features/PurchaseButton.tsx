"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { purchasePlan } from "@/helpers/credit";
import { formatMoney } from "@/helpers/currency";
import { minutesUntil } from "@/helpers/date";
import { useAuth } from "@/hooks/useAuth";
import { useLeadPurchase } from "@/hooks/useLeadPurchase";
import { path, type AppLocale } from "@/i18n/routing";
import type { LeadDetail } from "@/types/api";

/**
 * Bloque de desbloqueo del contacto.
 *
 * Tres estados posibles: contacto ya desbloqueado, reserva en curso pendiente de
 * pago, o bloqueado. La reserva en curso se muestra aparte porque el profesional
 * ya consumio una plaza y necesita saber que tiene un plazo para pagar.
 *
 * Sin la recarga mensual al dia no se ofrece comprar: se lleva a activarla. Con
 * saldo se anuncia cuanto se pagara con el (el importe real lo decide el API).
 */
export function PurchaseButton({ detail }: { detail: LeadDetail }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("lead");
  const purchase = useLeadPurchase();
  const auth = useAuth();

  if (detail.is_unlocked) {
    return null;
  }

  const reserved = detail.purchase?.status === "reserved";
  const minutesLeft = minutesUntil(detail.purchase?.reserved_until ?? null);
  const price = formatMoney(detail.lead.price, locale);
  const plan = purchasePlan(auth.me?.account ?? null, detail.lead.price);

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

      {plan.kind === "inactive" ? (
        <>
          <Alert tone="warning">{t("needsSubscription")}</Alert>
          <Link
            href={path(locale, "subscription")}
            className="flex min-h-[56px] w-full items-center justify-center rounded-control bg-accent px-8 text-[17px] font-semibold text-ink hover:bg-accent-hover"
          >
            {t("activateToBuy")}
          </Link>
        </>
      ) : (
        <>
          {plan.kind === "credit" && !reserved && (
            <Alert tone="info">
              {t("creditWillCover", {
                balance: formatMoney(auth.me?.account?.balance ?? detail.lead.price, locale),
              })}
            </Alert>
          )}
          {plan.kind === "mixed" && !reserved && (
            <Alert tone="info">
              {t("creditWillApply", {
                credit: formatMoney(plan.credit, locale),
                due: formatMoney(plan.due, locale),
              })}
            </Alert>
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
        </>
      )}

      {purchase.error && <Alert tone="error">{purchase.error}</Alert>}
    </div>
  );
}
