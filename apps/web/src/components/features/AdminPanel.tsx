"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Tag } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { AdminManualLeadForm } from "@/components/features/AdminManualLeadForm";
import { formatMoney } from "@/helpers/currency";
import { useApiError } from "@/hooks/useApiError";
import { type AppLocale } from "@/i18n/routing";
import { adminService, type AdminLeadFilters } from "@/services/admin.service";
import { leadsService } from "@/services/leads.service";
import type {
  AdminLead,
  AdminPurchase,
  Category,
  SubscriptionPrice,
} from "@/types/api";

const EMPTY_FILTERS: AdminLeadFilters = {};

/**
 * Operaciones de soporte sin mostrar PII del cliente: leads manuales, precios e
 * inventario. Las metricas viven en `AdminDashboard` y los usuarios en `AdminUsers`.
 */
export function AdminPanel() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tCommon = useTranslations("common");
  const translateError = useApiError();
  const [leads, setLeads] = useState<AdminLead[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filters, setFilters] = useState<AdminLeadFilters>(EMPTY_FILTERS);
  const [selectedLead, setSelectedLead] = useState<AdminLead | null>(null);
  const [purchases, setPurchases] = useState<AdminPurchase[]>([]);
  const [priceDrafts, setPriceDrafts] = useState<Record<string, string>>({});
  const [categoryId, setCategoryId] = useState("");
  const [categoryPrice, setCategoryPrice] = useState("");
  const [subscriptionPrice, setSubscriptionPrice] =
    useState<SubscriptionPrice | null>(null);
  const [subscriptionDraft, setSubscriptionDraft] = useState("");
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextLeads, nextCategories, nextSubscription] = await Promise.all([
        adminService.leads(filters, locale),
        leadsService.categories(locale),
        adminService.subscriptionPrice(locale),
      ]);
      setSubscriptionPrice(nextSubscription);
      setLeads(nextLeads.items);
      setCategories(nextCategories);
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [filters, locale, translateError]);

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

  async function showPurchases(lead: AdminLead): Promise<void> {
    setSelectedLead(lead);
    setPurchases([]);
    setError(null);
    try {
      setPurchases(await adminService.purchases(lead.id, locale));
    } catch (caught) {
      setError(translateError(caught));
    }
  }

  function updateFilter(key: keyof AdminLeadFilters, value: string): void {
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  return (
    <div className="space-y-8">
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {loading && <p className="text-help text-muted">{tCommon("loading")}</p>}

      <section className="grid gap-6 xl:grid-cols-2">
        <AdminManualLeadForm categories={categories} onCreated={() => void reload()} />

        <Card className="space-y-4">
          <h2 className="text-card-title font-bold text-ink">
            {t("categoryPricing.title")}
          </h2>
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
                adminService.setCategoryPrice(
                  categoryId,
                  Number(categoryPrice),
                  locale,
                ),
              )
            }
          >
            {t("categoryPricing.submit")}
          </Button>
        </Card>

        <Card className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-card-title font-bold text-ink">
              {t("subscriptionPrice.title")}
            </h2>
            <p className="text-sm text-secondary">
              {t("subscriptionPrice.body")}
            </p>
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

      <section className="space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-card-title font-bold text-ink">
              {t("leads.title")}
            </h2>
            <p className="text-sm text-secondary">{t("leads.subtitle")}</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <SelectField
              label={t("leads.status")}
              value={filters.status ?? ""}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value="">{t("leads.all")}</option>
              <option value="published">{t("status.published")}</option>
              <option value="exhausted">{t("status.exhausted")}</option>
              <option value="disabled">{t("status.disabled")}</option>
            </SelectField>
            <SelectField
              label={t("leads.source")}
              value={filters.source ?? ""}
              onChange={(event) => updateFilter("source", event.target.value)}
            >
              <option value="">{t("leads.all")}</option>
              <option value="organic">{t("source.organic")}</option>
              <option value="admin">{t("source.admin")}</option>
            </SelectField>
            <SelectField
              label={t("leads.category")}
              value={filters.categoryId ?? ""}
              onChange={(event) =>
                updateFilter("categoryId", event.target.value)
              }
            >
              <option value="">{t("leads.all")}</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </SelectField>
          </div>
        </header>

        <div className="grid gap-4 lg:grid-cols-2">
          {leads.map((lead) => (
            <Card key={lead.id} className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-ink">{lead.title}</h3>
                  <p className="text-sm text-secondary">
                    {t("leads.location", {
                      category: lead.category.name,
                      city: lead.city,
                    })}
                  </p>
                </div>
                <Tag tone={lead.status === "published" ? "trade" : "accent"}>
                  {t(`status.${lead.status}`)}
                </Tag>
              </div>
              <p className="line-clamp-2 text-sm text-secondary">
                {lead.description}
              </p>
              <p className="text-sm text-secondary">
                {t("leads.slots", {
                  sold: lead.purchases_count,
                  max: lead.max_purchases,
                })}
              </p>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                <TextField
                  label={t("leads.price")}
                  value={
                    priceDrafts[lead.id] ?? String(lead.price.amount_cents)
                  }
                  onChange={(event) =>
                    setPriceDrafts((current) => ({
                      ...current,
                      [lead.id]: event.target.value,
                    }))
                  }
                  inputMode="numeric"
                  type="number"
                  min="1"
                />
                <Button
                  className="self-end"
                  loading={saving}
                  onClick={() =>
                    void run(() =>
                      adminService.setLeadPrice(
                        lead.id,
                        Number(priceDrafts[lead.id] ?? lead.price.amount_cents),
                        locale,
                      ),
                    )
                  }
                >
                  {t("leads.savePrice")}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void showPurchases(lead)}
                >
                  {t("leads.purchases")}
                </Button>
                {lead.status === "disabled" ? (
                  <Button
                    size="sm"
                    loading={saving}
                    onClick={() =>
                      void run(() =>
                        adminService.republishLead(lead.id, locale),
                      )
                    }
                  >
                    {t("leads.republish")}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="danger"
                    loading={saving}
                    onClick={() =>
                      void run(() => adminService.disableLead(lead.id, locale))
                    }
                  >
                    {t("leads.disable")}
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      </section>

      {selectedLead && (
        <section className="space-y-4">
          <h2 className="text-card-title font-bold text-ink">
            {t("purchases.title", { lead: selectedLead.title })}
          </h2>
          {purchases.length === 0 ? (
            <Alert tone="info">{t("purchases.empty")}</Alert>
          ) : (
            purchases.map((entry) => (
              <Card key={entry.purchase.id} className="space-y-3">
                <p className="font-medium text-ink">
                  {entry.professional?.business_name ??
                    t("purchases.unknownProfessional")}
                </p>
                <p className="text-sm text-secondary">
                  {formatMoney(entry.purchase.amount, locale)} ·{" "}
                  {t(`purchaseStatus.${entry.purchase.status}`)}
                </p>
                <p className="text-sm text-secondary">
                  {t("purchases.reviews", { count: entry.review_count })}
                </p>
                <div className="flex flex-wrap items-end gap-2">
                  <TextField
                    className="min-w-64"
                    label={t("purchases.reviewNote")}
                    value={reviewNotes[entry.purchase.id] ?? ""}
                    onChange={(event) =>
                      setReviewNotes((current) => ({
                        ...current,
                        [entry.purchase.id]: event.target.value,
                      }))
                    }
                  />
                  <Button
                    loading={saving}
                    disabled={
                      (reviewNotes[entry.purchase.id] ?? "").trim().length < 3
                    }
                    onClick={() =>
                      void run(() =>
                        adminService.reviewPurchase(
                          entry.purchase.id,
                          reviewNotes[entry.purchase.id] ?? "",
                          locale,
                        ),
                      )
                    }
                  >
                    {t("purchases.markReview")}
                  </Button>
                </div>
              </Card>
            ))
          )}
        </section>
      )}

      <Button variant="secondary" onClick={() => void reload()}>
        {tCommon("retry")}
      </Button>
    </div>
  );
}
