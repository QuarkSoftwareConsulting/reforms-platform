"use client";

import { useTranslations } from "next-intl";

import { LeadCard } from "@/components/features/LeadCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Card";
import { SelectField } from "@/components/ui/Field";
import { useAuth } from "@/hooks/useAuth";
import { useProjectFilter } from "@/hooks/useProjectFilter";

const RADIUS_OPTIONS = [10, 25, 50, 100, 200] as const;

/** Explorador de solicitudes con filtros por oficio y radio. */
export function ProjectExplorer() {
  const t = useTranslations("projects");
  const tCommon = useTranslations("common");
  const auth = useAuth();
  const professional = auth.me?.professional ?? null;
  const filter = useProjectFilter(professional?.service_radius_km ?? null);

  const categories = professional?.categories ?? [];
  const effectiveRadius = filter.radiusKm ?? professional?.service_radius_km ?? 25;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold text-slate-900">{t("title")}</h1>
        <p className="text-slate-600">
          {t("subtitle", {
            total: filter.data?.total ?? 0,
            radius: effectiveRadius,
            city: professional?.city ?? professional?.postal_code ?? "",
          })}
        </p>
      </header>

      <Card className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label={t("filterCategory")}
          value={filter.categoryIds[0] ?? ""}
          onChange={(event) =>
            filter.setCategoryIds(event.target.value ? [event.target.value] : [])
          }
        >
          <option value="">{t("filterAll")}</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectField>

        <SelectField
          label={t("filterRadius")}
          value={String(effectiveRadius)}
          onChange={(event) => filter.setRadiusKm(Number(event.target.value))}
        >
          {RADIUS_OPTIONS.map((km) => (
            <option key={km} value={km}>
              {km} km
            </option>
          ))}
        </SelectField>
      </Card>

      {filter.error && (
        <Alert tone="error">
          <div className="flex items-center justify-between gap-3">
            <span>{filter.error}</span>
            <Button size="sm" variant="secondary" onClick={filter.reload}>
              {tCommon("retry")}
            </Button>
          </div>
        </Alert>
      )}

      {filter.loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-72" />
          ))}
        </div>
      )}

      {!filter.loading && !filter.error && filter.data?.items.length === 0 && (
        <Alert tone="info">{t("empty")}</Alert>
      )}

      {!filter.loading && filter.data && filter.data.items.length > 0 && (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filter.data.items.map((lead) => (
              <li key={lead.id}>
                <LeadCard lead={lead} />
              </li>
            ))}
          </ul>

          {filter.totalPages > 1 && (
            <nav className="flex items-center justify-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                disabled={filter.page === 0}
                onClick={() => filter.setPage(filter.page - 1)}
              >
                {tCommon("back")}
              </Button>
              <span className="text-sm text-slate-600">
                {filter.page + 1} / {filter.totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={filter.page + 1 >= filter.totalPages}
                onClick={() => filter.setPage(filter.page + 1)}
              >
                {tCommon("next")}
              </Button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
