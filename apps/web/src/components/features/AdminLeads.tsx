"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { AdminManualLeadForm } from "@/components/features/AdminManualLeadForm";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Tag } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { formatMoney } from "@/helpers/currency";
import { useApiError } from "@/hooks/useApiError";
import { type AppLocale } from "@/i18n/routing";
import { adminService, type AdminLeadFilters } from "@/services/admin.service";
import { leadsService } from "@/services/leads.service";
import type { AdminLead, AdminPurchase, Category } from "@/types/api";

const EMPTY_FILTERS: AdminLeadFilters = {};

/**
 * Inventario de leads sin mostrar PII del cliente: alta manual, moderacion, precio de
 * cada contacto y sus compras.
 */
export function AdminLeads() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const tCommon = useTranslations("common");
  const translateError = useApiError();
  const [leads, setLeads] = useState<AdminLead[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filters, setFilters] = useState<AdminLeadFilters>(EMPTY_FILTERS);
  const [showManual, setShowManual] = useState(false);
  const [selectedLead, setSelectedLead] = useState<AdminLead | null>(null);
  const [purchases, setPurchases] = useState<AdminPurchase[] | null>(null);
  const [priceDrafts, setPriceDrafts] = useState<Record<string, string>>({});
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextLeads, nextCategories] = await Promise.all([
        adminService.leads(filters, locale),
        leadsService.categories(locale),
      ]);
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
    setPurchases(null);
    setError(null);
    try {
      setPurchases(await adminService.purchases(lead.id, locale));
    } catch (caught) {
      setSelectedLead(null);
      setError(translateError(caught));
    }
  }

  function closePurchases(): void {
    setSelectedLead(null);
    setPurchases(null);
  }

  function updateFilter(key: keyof AdminLeadFilters, value: string): void {
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-h2 font-bold text-ink">{t("leads.title")}</h2>
          <p className="text-help text-muted">{t("leads.subtitle")}</p>
        </div>
        <Button
          variant="secondary"
          aria-expanded={showManual}
          onClick={() => setShowManual((open) => !open)}
        >
          {showManual ? t("leads.hideManual") : t("leads.showManual")}
        </Button>
      </header>

      {/* El formulario es largo: plegado por defecto para que el inventario quede a la vista. */}
      {showManual && (
        <AdminManualLeadForm categories={categories} onCreated={() => void reload()} />
      )}

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

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

      {loading && <p className="text-help text-muted">{tCommon("loading")}</p>}
      {!loading && leads.length === 0 && <p className="text-secondary">{t("leads.empty")}</p>}

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
                variant="secondary"
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
                  variant="secondary"
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

      {/* En un modal y no al final del listado: antes salian lejos de la tarjeta pulsada. */}
      <Modal
        open={selectedLead !== null}
        title={selectedLead ? t("purchases.title", { lead: selectedLead.title }) : ""}
        onClose={closePurchases}
        dismissible={!saving}
        actions={
          <Button type="button" variant="secondary" disabled={saving} onClick={closePurchases}>
            {tCommon("close")}
          </Button>
        }
      >
        {purchases === null ? (
          <p className="text-help text-muted">{tCommon("loading")}</p>
        ) : purchases.length === 0 ? (
          <Alert tone="info">{t("purchases.empty")}</Alert>
        ) : (
          <ul className="divide-y divide-divider">
            {purchases.map((entry) => (
              <li key={entry.purchase.id} className="space-y-2 py-3">
                <p className="font-medium text-ink">
                  {entry.professional?.business_name ?? t("purchases.unknownProfessional")}
                </p>
                <p className="text-sm text-secondary">
                  {formatMoney(entry.purchase.amount, locale)} ·{" "}
                  {t(`purchaseStatus.${entry.purchase.status}`)} ·{" "}
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
                    variant="secondary"
                    loading={saving}
                    disabled={(reviewNotes[entry.purchase.id] ?? "").trim().length < 3}
                    onClick={() =>
                      void run(async () => {
                        await adminService.reviewPurchase(
                          entry.purchase.id,
                          reviewNotes[entry.purchase.id] ?? "",
                          locale,
                        );
                        // El contador de notas de este modal no lo refresca `reload`.
                        if (selectedLead) await showPurchases(selectedLead);
                      })
                    }
                  >
                    {t("purchases.markReview")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </div>
  );
}
