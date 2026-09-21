"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton, Tag } from "@/components/ui/Card";
import { SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import { PhotoUploader } from "@/components/features/PhotoUploader";
import { formatMoney } from "@/helpers/currency";
import { useApiError } from "@/hooks/useApiError";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { type AppLocale } from "@/i18n/routing";
import { adminService, type AdminLeadFilters } from "@/services/admin.service";
import { leadsService } from "@/services/leads.service";
import type {
  AdminLead,
  AdminMetrics,
  AdminProfessional,
  AdminPurchase,
  Category,
} from "@/types/api";

const EMPTY_FILTERS: AdminLeadFilters = {};

/** Consolida las operaciones de soporte sin mostrar PII del cliente. */
export function AdminPanel() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tCommon = useTranslations("common");
  const translateError = useApiError();
  const photoUpload = usePhotoUpload();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [leads, setLeads] = useState<AdminLead[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [professionals, setProfessionals] = useState<AdminProfessional[]>([]);
  const [filters, setFilters] = useState<AdminLeadFilters>(EMPTY_FILTERS);
  const [selectedLead, setSelectedLead] = useState<AdminLead | null>(null);
  const [purchases, setPurchases] = useState<AdminPurchase[]>([]);
  const [priceDrafts, setPriceDrafts] = useState<Record<string, string>>({});
  const [categoryId, setCategoryId] = useState("");
  const [categoryPrice, setCategoryPrice] = useState("");
  const [professionalQuery, setProfessionalQuery] = useState("");
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextMetrics, nextLeads, nextCategories, nextProfessionals] = await Promise.all([
        adminService.metrics(locale),
        adminService.leads(filters, locale),
        leadsService.categories(locale),
        adminService.professionals(professionalQuery, locale),
      ]);
      setMetrics(nextMetrics);
      setLeads(nextLeads.items);
      setCategories(nextCategories);
      setProfessionals(nextProfessionals.items);
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [filters, locale, professionalQuery, translateError]);

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

  async function submitManualLead(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const acceptedAt = new Date(String(form.get("accepted_at"))).toISOString();
    await run(async () => {
      await adminService.createLead(
        {
          category_id: String(form.get("category_id")),
          title: String(form.get("title")),
          description: String(form.get("description")),
          postal_code: String(form.get("postal_code")),
          client_name: String(form.get("client_name")),
          client_phone: String(form.get("client_phone")),
          client_email: String(form.get("client_email")) || null,
          photo_keys: photoUpload.storageKeys,
          consent: {
            policy_version: String(form.get("policy_version")),
            accepted_at: acceptedAt,
            channel: String(form.get("channel")),
            campaign_reference: String(form.get("campaign_reference")) || null,
          },
        },
        locale,
      );
      event.currentTarget.reset();
    });
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
      <header className="space-y-1">
        <h1 className="text-h1 font-bold text-ink">{t("title")}</h1>
        <p className="text-secondary">{t("subtitle")}</p>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {loading || !metrics ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label={t("metrics.leads")} value={String(metrics.leads_total)} />
          <Metric label={t("metrics.professionals")} value={String(metrics.professionals_total)} />
          <Metric label={t("metrics.coverage")} value={formatPercent(metrics.coverage_rate)} />
          <Metric label={t("metrics.liquidity")} value={metrics.liquidity.toFixed(2)} />
          <Metric label={t("metrics.paidPurchases")} value={String(metrics.paid_purchases)} />
          <Metric
            label={t("metrics.revenue")}
            value={Object.values(metrics.revenue_by_currency)
              .map((money) => formatMoney(money, locale))
              .join(" · ") || t("metrics.none")}
          />
          <Metric label={t("metrics.organic")} value={String(metrics.leads_organic)} />
          <Metric label={t("metrics.manual")} value={String(metrics.leads_admin)} />
        </section>
      )}

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 text-card-title font-bold text-ink">{t("manual.title")}</h2>
          <form className="grid gap-4 sm:grid-cols-2" onSubmit={(event) => void submitManualLead(event)}>
            <SelectField label={t("manual.category")} name="category_id" required>
              <option value="">{t("manual.categoryPlaceholder")}</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </SelectField>
            <TextField label={t("manual.titleLabel")} name="title" required />
            <TextAreaField className="sm:col-span-2" label={t("manual.description")} name="description" required />
            <TextField label={t("manual.postalCode")} name="postal_code" required />
            <TextField label={t("manual.name")} name="client_name" required />
            <TextField label={t("manual.phone")} name="client_phone" required />
            <TextField label={t("manual.email")} name="client_email" type="email" />
            <TextField label={t("manual.channel")} name="channel" required />
            <TextField label={t("manual.policy")} name="policy_version" required />
            <TextField label={t("manual.acceptedAt")} name="accepted_at" type="datetime-local" required />
            <TextField label={t("manual.campaign")} name="campaign_reference" />
            <div className="sm:col-span-2">
              <PhotoUploader upload={photoUpload} />
            </div>
            <div className="sm:col-span-2">
              <Button loading={saving} type="submit">
                {t("manual.submit")}
              </Button>
            </div>
          </form>
        </Card>

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
              void run(() => adminService.setCategoryPrice(categoryId, Number(categoryPrice), locale))
            }
          >
            {t("categoryPricing.submit")}
          </Button>
        </Card>
      </section>

      <section className="space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-card-title font-bold text-ink">{t("leads.title")}</h2>
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
              onChange={(event) => updateFilter("categoryId", event.target.value)}
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
                    {t("leads.location", { category: lead.category.name, city: lead.city })}
                  </p>
                </div>
                <Tag tone={lead.status === "published" ? "trade" : "accent"}>
                  {t(`status.${lead.status}`)}
                </Tag>
              </div>
              <p className="line-clamp-2 text-sm text-secondary">{lead.description}</p>
              <p className="text-sm text-secondary">
                {t("leads.slots", { sold: lead.purchases_count, max: lead.max_purchases })}
              </p>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                <TextField
                  label={t("leads.price")}
                  value={priceDrafts[lead.id] ?? String(lead.price.amount_cents)}
                  onChange={(event) =>
                    setPriceDrafts((current) => ({ ...current, [lead.id]: event.target.value }))
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
                <Button size="sm" variant="secondary" onClick={() => void showPurchases(lead)}>
                  {t("leads.purchases")}
                </Button>
                {lead.status === "disabled" ? (
                  <Button
                    size="sm"
                    loading={saving}
                    onClick={() => void run(() => adminService.republishLead(lead.id, locale))}
                  >
                    {t("leads.republish")}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="danger"
                    loading={saving}
                    onClick={() => void run(() => adminService.disableLead(lead.id, locale))}
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
                  {entry.professional?.business_name ?? t("purchases.unknownProfessional")}
                </p>
                <p className="text-sm text-secondary">
                  {formatMoney(entry.purchase.amount, locale)} · {t(`purchaseStatus.${entry.purchase.status}`)}
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
                      setReviewNotes((current) => ({ ...current, [entry.purchase.id]: event.target.value }))
                    }
                  />
                  <Button
                    loading={saving}
                    disabled={(reviewNotes[entry.purchase.id] ?? "").trim().length < 3}
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

      <section className="space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-card-title font-bold text-ink">{t("professionals.title")}</h2>
            <p className="text-sm text-secondary">{t("professionals.subtitle")}</p>
          </div>
          <TextField
            label={t("professionals.search")}
            value={professionalQuery}
            onChange={(event) => setProfessionalQuery(event.target.value)}
          />
        </header>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {professionals.map((professional) => (
            <Card key={professional.id} className="space-y-2">
              <h3 className="font-semibold text-ink">{professional.business_name}</h3>
              <p className="text-sm text-secondary">
                {t("professionals.location", {
                  city: professional.city ?? professional.postal_code,
                  distance: professional.service_radius_km,
                })}
              </p>
              <p className="text-sm text-secondary">
                {professional.categories.map((category) => category.name).join(", ")}
              </p>
            </Card>
          ))}
        </div>
      </section>

      <Button variant="secondary" onClick={() => void reload()}>
        {tCommon("retry")}
      </Button>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="text-sm text-secondary">{label}</p>
      <p className="mt-1 text-h2 font-bold text-ink">{value}</p>
    </Card>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
