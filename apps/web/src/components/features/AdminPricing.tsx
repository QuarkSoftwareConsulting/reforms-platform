"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { formatMoney } from "@/helpers/currency";
import { useApiError } from "@/hooks/useApiError";
import { type AppLocale } from "@/i18n/routing";
import { adminService } from "@/services/admin.service";
import { leadsService } from "@/services/leads.service";
import type { Category, SubscriptionPrice } from "@/types/api";

/**
 * Precios que fija el admin: el sugerido de cada oficio y la mensualidad. El precio de
 * un contacto concreto se decide en su tarjeta, en `AdminLeads`.
 */
export function AdminPricing() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tCommon = useTranslations("common");
  const translateError = useApiError();
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [categoryPrice, setCategoryPrice] = useState("");
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
      const [nextCategories, nextSubscription] = await Promise.all([
        leadsService.categories(locale),
        adminService.subscriptionPrice(locale),
      ]);
      setCategories(nextCategories);
      setSubscriptionPrice(nextSubscription);
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
        <Card className="space-y-4">
          <h2 className="text-card-title font-bold text-ink">{t("categoryPricing.title")}</h2>
          <SelectField
            label={t("categoryPricing.category")}
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
          >
            <option value="">{t("categoryPricing.placeholder")}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("categoryPricing.amount")}
            value={categoryPrice}
            onChange={(event) => setCategoryPrice(event.target.value)}
            inputMode="numeric"
            type="number"
            min="1"
          />
          <Button
            loading={saving}
            disabled={!categoryId || Number(categoryPrice) < 1}
            onClick={() =>
              void run(() =>
                adminService.setCategoryPrice(categoryId, Number(categoryPrice), locale),
              )
            }
          >
            {t("categoryPricing.submit")}
          </Button>
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
