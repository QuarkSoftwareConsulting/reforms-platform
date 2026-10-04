"use client";

import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Card, Tag } from "@/components/ui/Card";
import { SelectField, TextField } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { formatMoney } from "@/helpers/currency";
import { formatDateTime } from "@/helpers/date";
import { useAdminPurchases } from "@/hooks/useAdminPurchases";
import type { AppLocale } from "@/i18n/routing";
import type { PurchaseStatus } from "@/types/api";

const STATUSES: PurchaseStatus[] = ["paid", "reserved", "refunded", "expired", "failed"];

/**
 * Todas las compras: quien compro cada contacto, cuando y por cuanto. Muestra la
 * solicitud por su titulo y su zona: el contacto del cliente no sale nunca de aqui.
 */
export function AdminPurchases() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const purchases = useAdminPurchases();
  const { filters } = purchases;

  return (
    <Card className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-h2 font-bold text-ink">{t("allPurchases.title")}</h2>
        <p className="text-help text-muted">{t("allPurchases.subtitle")}</p>
      </header>

      {purchases.error && <Alert tone="error">{purchases.error}</Alert>}

      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField
          label={t("allPurchases.status")}
          value={filters.status ?? ""}
          onChange={(event) =>
            purchases.setFilters({
              ...filters,
              status: (event.target.value || undefined) as PurchaseStatus | undefined,
            })
          }
        >
          <option value="">{t("allPurchases.all")}</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {t(`purchaseStatus.${status}`)}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("allPurchases.from")}
          type="date"
          value={filters.from ?? ""}
          onChange={(event) =>
            purchases.setFilters({ ...filters, from: event.target.value || undefined })
          }
        />
        <TextField
          label={t("allPurchases.to")}
          type="date"
          value={filters.to ?? ""}
          onChange={(event) =>
            purchases.setFilters({ ...filters, to: event.target.value || undefined })
          }
        />
      </div>

      {!purchases.loading && purchases.items.length === 0 ? (
        <p className="text-secondary">{t("allPurchases.empty")}</p>
      ) : (
        <ul
          className={`divide-y divide-divider rounded-option border border-line ${purchases.loading ? "opacity-60" : ""}`}
          aria-busy={purchases.loading}
        >
          {purchases.items.map(({ purchase, professional, lead, review_count }) => (
            <li
              key={purchase.id}
              className="grid gap-2 px-4 py-3 sm:grid-cols-[1fr_auto] sm:items-start"
            >
              <div className="min-w-0 space-y-1">
                <p className="font-semibold text-ink">
                  {lead ? lead.title : t("allPurchases.unknownLead")}
                </p>
                <p className="text-help text-muted">
                  {[lead?.category?.name, lead?.city].filter(Boolean).join(" · ")}
                </p>
                <p className="text-help text-secondary">
                  {t("allPurchases.professional")}:{" "}
                  {professional?.business_name ?? t("purchases.unknownProfessional")}
                </p>
                <p className="text-help text-muted">
                  {formatDateTime(purchase.created_at, locale)}
                  {review_count > 0 && ` · ${t("purchases.reviews", { count: review_count })}`}
                </p>
              </div>
              <div className="space-y-1 sm:text-right">
                <p className="font-semibold text-ink">{formatMoney(purchase.amount, locale)}</p>
                {purchase.credit_applied && purchase.credit_applied.amount_cents > 0 && (
                  <p className="text-help text-muted">
                    {t("allPurchases.paidWithCredit", {
                      amount: formatMoney(purchase.credit_applied, locale),
                    })}
                  </p>
                )}
                <Tag tone={purchase.status === "paid" ? "trade" : "neutral"}>
                  {t(`purchaseStatus.${purchase.status}`)}
                </Tag>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Pagination
        page={purchases.page}
        pages={purchases.pages}
        label={t("pagination.page", { page: purchases.page + 1, pages: purchases.pages })}
        previous={t("pagination.previous")}
        next={t("pagination.next")}
        onChange={purchases.setPage}
      />
    </Card>
  );
}
