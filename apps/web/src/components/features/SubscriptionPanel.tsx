"use client";

import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton, Tag } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { formatDate } from "@/helpers/date";
import { useApiError } from "@/hooks/useApiError";
import { useAuth } from "@/hooks/useAuth";
import type { AppLocale } from "@/i18n/routing";
import { subscriptionService } from "@/services/subscription.service";
import type { Account } from "@/types/api";

/** Espera de confirmacion del webhook al volver del checkout de la recarga. */
const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 10;

/** Estado de la recarga mensual, saldo y movimientos. */
export function SubscriptionPanel() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("subscription");
  const translateError = useApiError();
  const auth = useAuth();
  const searchParams = useSearchParams();
  const returnStatus = searchParams.get("status");

  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);
  const pollCount = useRef(0);
  const refreshedMe = useRef(false);
  const { refreshMe } = auth;

  const load = useCallback(async () => {
    try {
      setAccount(await subscriptionService.account(locale));
      setError(null);
    } catch (caught) {
      setError(translateError(caught));
    }
  }, [locale, translateError]);

  useEffect(() => {
    void load();
  }, [load]);

  // Al volver del checkout el cobro puede seguir sin confirmar (con SEPA, dias).
  // Se reintenta unos segundos por si fue con tarjeta; si no, queda "pendiente".
  useEffect(() => {
    if (returnStatus !== "success" || account === null) return;
    if (account.is_active) {
      // Una sola vez: el resto de la app (banner, boton de compra) lee `me`.
      if (!refreshedMe.current) {
        refreshedMe.current = true;
        void refreshMe();
      }
      return;
    }
    if (pollCount.current >= MAX_POLLS) return;
    const timer = setTimeout(() => {
      pollCount.current += 1;
      void load();
    }, POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [returnStatus, account, load, refreshMe]);

  const redirect = async (action: () => Promise<string>) => {
    setRedirecting(true);
    setError(null);
    try {
      // Navegacion completa: el checkout y el portal estan en otro dominio.
      window.location.assign(await action());
    } catch (caught) {
      setError(translateError(caught));
      setRedirecting(false);
    }
  };

  if (account === null) {
    return error ? <Alert tone="error">{error}</Alert> : <Skeleton className="h-96 w-full" />;
  }

  const amount = formatMoney(account.topup_amount, locale);
  const canStart = account.status === "none" || account.status === "canceled";
  const notice = {
    none: null,
    active: null,
    pending: t("pendingNotice"),
    past_due: t("pastDueNotice"),
    canceled: t("canceledNotice"),
  }[account.status];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-h1 font-bold text-ink">{t("title")}</h1>
        <p className="text-secondary">{t("subtitle", { amount })}</p>
      </header>

      {returnStatus === "success" && !account.is_active && (
        <Alert tone="info">{t("checkoutSuccess")}</Alert>
      )}
      {returnStatus === "cancelled" && <Alert tone="warning">{t("checkoutCancelled")}</Alert>}

      <Card className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-[11px] uppercase tracking-[0.7px] text-muted">
            {t("statusLabel")}
          </span>
          <Tag tone={account.is_active ? "trade" : "accent"}>{t(`status.${account.status}`)}</Tag>
        </div>

        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-[13px] text-secondary">{t("balanceLabel")}</dt>
            <dd className="text-[24px] font-bold text-brand">
              {formatMoney(account.balance, locale)}
            </dd>
          </div>
          <div>
            <dt className="text-[13px] text-secondary">{t("topupLabel")}</dt>
            <dd className="text-[24px] font-bold text-ink">{amount}</dd>
            {account.current_period_end && account.is_active && (
              <dd className="text-[13px] text-secondary">
                {t("renewsOn", { date: formatDate(account.current_period_end, locale) })}
              </dd>
            )}
          </div>
        </dl>

        {account.debt && account.debt.amount_cents > 0 && (
          <Alert tone="warning">
            {t("debtNotice", { debt: formatMoney(account.debt, locale) })}
          </Alert>
        )}
        {notice && <Alert tone="warning">{notice}</Alert>}

        {canStart ? (
          <div className="space-y-3">
            <Button
              variant="accent"
              size="lg"
              fullWidth
              loading={redirecting}
              onClick={() =>
                void redirect(async () => (await subscriptionService.startCheckout(locale)).checkout_url)
              }
            >
              {redirecting
                ? t("redirecting")
                : account.status === "canceled"
                  ? t("reactivate")
                  : t("activate", { amount })}
            </Button>
            <p className="text-[13px] text-secondary">{t("sepaNotice")}</p>
          </div>
        ) : (
          account.can_manage_billing && (
            <Button
              variant="secondary"
              fullWidth
              loading={redirecting}
              onClick={() =>
                void redirect(async () => (await subscriptionService.openPortal(locale)).url)
              }
            >
              {redirecting ? t("redirecting") : t("manage")}
            </Button>
          )
        )}

        {error && <Alert tone="error">{error}</Alert>}
      </Card>

      <Card className="space-y-3">
        <h2 className="text-card-title font-semibold text-ink">{t("historyTitle")}</h2>
        {account.entries.length === 0 ? (
          <p className="text-secondary">{t("historyEmpty")}</p>
        ) : (
          <ul className="divide-y divide-divider">
            {account.entries.map((entry) => (
              <li
                key={`${entry.kind}-${entry.created_at}-${entry.signed_amount_cents}`}
                className="flex items-center justify-between gap-3 py-2.5"
              >
                <span>
                  <span className="block text-ink">{t(`entry.${entry.kind}`)}</span>
                  <span className="text-[13px] text-secondary">
                    {formatDate(entry.created_at, locale)}
                  </span>
                </span>
                <span
                  className={
                    entry.signed_amount_cents >= 0 ? "font-semibold text-brand" : "text-ink"
                  }
                >
                  {entry.signed_amount_cents >= 0 ? "+" : "-"}
                  {formatMoney(entry.amount, locale)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
