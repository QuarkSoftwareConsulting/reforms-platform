"use client";

import { useLocale, useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Card, Skeleton } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { ColumnChart, type ColumnDatum } from "@/components/ui/ColumnChart";
import { formatMoney } from "@/helpers/currency";
import { formatDay } from "@/helpers/date";
import { RANGE_PRESETS, useAdminDashboard, type RangePreset } from "@/hooks/useAdminDashboard";
import type { AppLocale } from "@/i18n/routing";
import type { DailyMetrics, Money } from "@/types/api";

const DEFAULT_CURRENCY = "EUR";

/** Divisa a graficar: la primera con importes en el periodo. Nunca se mezclan divisas. */
function chartCurrency(points: DailyMetrics[], key: "revenue_by_currency" | "topup_revenue_by_currency") {
  for (const point of points) {
    const [currency] = Object.keys(point[key]);
    if (currency) return currency;
  }
  return DEFAULT_CURRENCY;
}

function moneyOf(cents: number, currency: string): Money {
  return { amount_cents: cents, currency, formatted: "" };
}

/**
 * Metricas acumuladas y actividad diaria. Cada medida va en su propia grafica: tienen
 * escalas distintas (unidades frente a euros) y un doble eje confunde.
 */
export function AdminDashboard() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("admin");
  const dashboard = useAdminDashboard();
  const { metrics, series } = dashboard;

  const points = series?.points ?? [];
  const revenueCurrency = chartCurrency(points, "revenue_by_currency");
  const topupCurrency = chartCurrency(points, "topup_revenue_by_currency");
  const count = (pick: (point: DailyMetrics) => number): ColumnDatum[] =>
    points.map((point) => ({
      label: formatDay(point.day, locale),
      value: pick(point),
      display: String(pick(point)),
    }));
  const money = (
    key: "revenue_by_currency" | "topup_revenue_by_currency",
    currency: string,
  ): ColumnDatum[] =>
    points.map((point) => {
      const cents = point[key][currency]?.amount_cents ?? 0;
      return {
        label: formatDay(point.day, locale),
        value: cents,
        display: formatMoney(moneyOf(cents, currency), locale),
      };
    });
  const moneyTick = (currency: string) => (cents: number) =>
    formatMoney(moneyOf(cents, currency), locale);
  const tableColumns: [string, string] = [t("dashboard.day"), t("dashboard.value")];

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-h1 font-bold text-ink">{t("title")}</h1>
          <p className="text-secondary">{t("subtitle")}</p>
        </div>
        <ChipGroup
          label={t("dashboard.range")}
          name="dashboard-range"
          options={RANGE_PRESETS.map((days) => ({
            value: String(days),
            label: t("dashboard.lastDays", { days }),
          }))}
          selected={[String(dashboard.days)]}
          onToggle={(value) => dashboard.setDays(Number(value) as RangePreset)}
        />
      </header>

      {dashboard.error && <Alert tone="error">{dashboard.error}</Alert>}

      {!metrics ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label={t("metrics.leads")} value={String(metrics.leads_total)} />
          <Metric label={t("dashboard.published")} value={String(metrics.leads_published)} />
          <Metric label={t("dashboard.exhausted")} value={String(metrics.leads_exhausted)} />
          <Metric label={t("metrics.professionals")} value={String(metrics.professionals_total)} />
          <Metric label={t("metrics.paidPurchases")} value={String(metrics.paid_purchases)} />
          <Metric label={t("dashboard.paidLeads")} value={String(metrics.paid_leads)} />
          <Metric label={t("metrics.coverage")} value={formatPercent(metrics.coverage_rate)} />
          <Metric label={t("metrics.liquidity")} value={metrics.liquidity.toFixed(2)} />
          <Metric
            label={t("metrics.revenue")}
            value={joinMoney(metrics.revenue_by_currency, locale) || t("metrics.none")}
          />
          <Metric
            label={t("dashboard.topupRevenue")}
            value={joinMoney(metrics.topup_revenue_by_currency, locale) || t("metrics.none")}
          />
          <Metric label={t("activeAccounts")} value={String(metrics.active_accounts)} />
          <Metric label={t("metrics.organic")} value={String(metrics.leads_organic)} />
          <Metric label={t("metrics.manual")} value={String(metrics.leads_admin)} />
        </div>
      )}

      {series && (
        // Al recargar se conserva el dibujo anterior atenuado: sin saltos de maquetacion.
        <div
          className={`grid gap-4 lg:grid-cols-2 ${dashboard.loading ? "opacity-60" : ""}`}
          aria-busy={dashboard.loading}
        >
          <Card>
            <ColumnChart
              title={t("dashboard.leadsChart")}
              data={count((point) => point.leads_created)}
              tableLabel={t("dashboard.showTable")}
              columns={tableColumns}
            />
          </Card>
          <Card>
            <ColumnChart
              title={t("dashboard.purchasesChart")}
              data={count((point) => point.paid_purchases)}
              tableLabel={t("dashboard.showTable")}
              columns={tableColumns}
            />
          </Card>
          <Card>
            <ColumnChart
              title={t("dashboard.revenueChart", { currency: revenueCurrency })}
              data={money("revenue_by_currency", revenueCurrency)}
              tableLabel={t("dashboard.showTable")}
              columns={tableColumns}
              formatTick={moneyTick(revenueCurrency)}
            />
          </Card>
          <Card>
            <ColumnChart
              title={t("dashboard.topupsChart", { currency: topupCurrency })}
              data={money("topup_revenue_by_currency", topupCurrency)}
              tableLabel={t("dashboard.showTable")}
              columns={tableColumns}
              formatTick={moneyTick(topupCurrency)}
            />
          </Card>
        </div>
      )}
    </section>
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

function joinMoney(amounts: Record<string, Money>, locale: AppLocale): string {
  return Object.values(amounts)
    .map((amount) => formatMoney(amount, locale))
    .join(" · ");
}
