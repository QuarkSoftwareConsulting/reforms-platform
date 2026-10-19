"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextField } from "@/components/ui/Field";
import { formatMoney } from "@/helpers/currency";
import { useApiError } from "@/hooks/useApiError";
import { path, type AppLocale } from "@/i18n/routing";
import { adminService } from "@/services/admin.service";
import type { SubscriptionPrice } from "@/types/api";

/**
 * Precios que fija el admin: la mensualidad. El sugerido de cada oficio se edita con el
 * resto de la categoria en `AdminCatalog`, y el de un contacto concreto en su tarjeta,
 * en `AdminLeads`.
 */
export function AdminPricing() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tCommon = useTranslations("common");
  const translateError = useApiError();
  const [subscriptionPrice, setSubscriptionPrice] = useState<SubscriptionPrice | null>(null);
  const [subscriptionDraft, setSubscriptionDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSubscriptionPrice(await adminService.subscriptionPrice(locale));
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [locale, translateError]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function run(action: () => Promise<unknown>): Promise<void> {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(t("saved"));
      await reload();
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {loading && <p className="text-help text-muted">{tCommon("loading")}</p>}

      <section className="grid gap-6 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-card-title font-bold text-ink">{t("categoryPricing.title")}</h2>
          <p className="text-sm text-secondary">{t("categoryPricing.body")}</p>
          <Link
            href={path(locale, "admin", "/catalogo")}
            className="inline-block text-sm font-semibold text-brand underline underline-offset-4 hover:text-brand-hover"
          >
            {t("categoryPricing.link")}
          </Link>
        </Card>

        <Card className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-card-title font-bold text-ink">{t("subscriptionPrice.title")}</h2>
            <p className="text-sm text-secondary">{t("subscriptionPrice.body")}</p>
          </div>
          {subscriptionPrice && (
            <p className="text-sm text-ink">
              {t("subscriptionPrice.current", {
                amount: formatMoney(subscriptionPrice.amount, locale),
              })}{" "}
              {subscriptionPrice.is_default && t("subscriptionPrice.default")}
            </p>
          )}
          {subscriptionPrice && !subscriptionPrice.configured && (
            <Alert tone="warning">{t("subscriptionPrice.notConfigured")}</Alert>
          )}
          <TextField
            label={t("subscriptionPrice.label")}
            value={subscriptionDraft}
            onChange={(event) => setSubscriptionDraft(event.target.value)}
            inputMode="decimal"
            type="number"
            min="0.5"
            step="0.01"
          />
          <Button
            variant="secondary"
            loading={saving}
            disabled={!(Number(subscriptionDraft) >= 0.5)}
            onClick={() =>
              void run(async () => {
                // El importe viaja en centimos, como todo `Money`.
                const cents = Math.round(Number(subscriptionDraft) * 100);
                await adminService.setSubscriptionPrice(cents, locale);
                setSubscriptionDraft("");
              })
            }
          >
            {t("subscriptionPrice.save")}
          </Button>
        </Card>
      </section>
    </div>
  );
}
