"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { ContactPanel } from "@/components/features/ContactPanel";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Badge, Card, Skeleton } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { formatDate } from "@/helpers/date";
import { useApiError } from "@/hooks/useApiError";
import { path, type AppLocale } from "@/i18n/routing";
import { paymentService } from "@/services/payment.service";
import type { PurchasedLead, PurchaseStatus } from "@/types/api";

const STATUS_TONES: Record<PurchaseStatus, "success" | "warning" | "neutral"> = {
  paid: "success",
  reserved: "warning",
  expired: "neutral",
  failed: "neutral",
  refunded: "neutral",
};

/** Espera de confirmacion del webhook al volver de Stripe. */
const POLL_INTERVAL_MS = 2500;
const MAX_POLLS = 8;

export function PurchaseHistory() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("purchases");
  const translateError = useApiError();
  const searchParams = useSearchParams();

  const justPurchasedId = searchParams.get("purchase");
  const returnedFromCheckout = searchParams.get("status") === "success";

  const [entries, setEntries] = useState<PurchasedLead[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollCount = useRef(0);

  const load = useCallback(async (): Promise<PurchasedLead[] | null> => {
    try {
      const result = await paymentService.myPurchases(locale);
      setEntries(result);
      setError(null);
      return result;
    } catch (caught) {
      setError(translateError(caught));
      return null;
    }
  }, [locale, translateError]);

  useEffect(() => {
    void load();
  }, [load]);

  // Al volver de la pasarela el webhook puede no haber llegado todavia. Se
  // reintenta unas pocas veces en vez de mostrar "pendiente" para siempre.
  useEffect(() => {
    if (!returnedFromCheckout || !justPurchasedId || entries === null) return;

    const target = entries.find((entry) => entry.purchase.id === justPurchasedId);
    if (target?.is_unlocked || pollCount.current >= MAX_POLLS) return;

    const timer = setTimeout(() => {
      pollCount.current += 1;
      void load();
    }, POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [returnedFromCheckout, justPurchasedId, entries, load]);

  const justPurchased = entries?.find((entry) => entry.purchase.id === justPurchasedId);
  const awaitingWebhook = returnedFromCheckout && justPurchased && !justPurchased.is_unlocked;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold text-slate-900">{t("title")}</h1>
        <p className="text-slate-600">{t("subtitle")}</p>
      </header>

      {returnedFromCheckout && justPurchased?.is_unlocked && (
        <Alert tone="success">{t("paymentSuccess")}</Alert>
      )}
      {awaitingWebhook && <Alert tone="info">{t("paymentPending")}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      {entries === null && !error && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {entries?.length === 0 && (
        <Card className="space-y-4 text-center">
          <p className="text-slate-600">{t("empty")}</p>
          <Link href={path(locale, "projects")}>
            <Button>{t("browseProjects")}</Button>
          </Link>
        </Card>
      )}

      {entries && entries.length > 0 && (
        <ul className="space-y-4">
          {entries.map((entry) => (
            <li key={entry.purchase.id}>
              <Card className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="brand">{entry.category.name}</Badge>
                      <Badge tone={STATUS_TONES[entry.purchase.status]}>
                        {t(`status.${entry.purchase.status}`)}
                      </Badge>
                    </div>
                    <h2 className="font-semibold text-slate-900">{entry.title}</h2>
                    <p className="text-sm text-slate-500">
                      {entry.city}, {entry.province}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-semibold text-slate-900">
                      {formatMoney(entry.purchase.amount, locale)}
                    </p>
                    {entry.purchase.paid_at && (
                      <p className="text-slate-500">
                        {t("purchasedOn", { date: formatDate(entry.purchase.paid_at, locale) })}
                      </p>
                    )}
                  </div>
                </div>

                {entry.contact && <ContactPanel contact={entry.contact} />}

                {!entry.contact && entry.purchase.status === "reserved" && (
                  <Link
                    href={`${path(locale, "projects")}/${entry.lead_id}`}
                    className="inline-block text-sm font-semibold text-brand-700 hover:underline"
                  >
                    {t("status.reserved")} →
                  </Link>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
