import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Badge, Card } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { formatRelative } from "@/helpers/date";
import { formatDistance } from "@/helpers/distance";
import { path } from "@/i18n/routing";
import type { AppLocale } from "@/i18n/routing";
import type { LeadPublic } from "@/types/api";

/**
 * Tarjeta del explorador.
 *
 * Recibe un `LeadPublic`, cuyo tipo no incluye datos de contacto: es
 * estructuralmente imposible que esta tarjeta filtre la PII del cliente.
 */
export function LeadCard({ lead }: { lead: LeadPublic }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("projects");
  const tLead = useTranslations("lead");
  const cover = lead.photo_urls[0];

  return (
    <Card className="flex h-full flex-col gap-3 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <Badge tone="brand">{lead.category.name}</Badge>
        {lead.already_purchased ? (
          <Badge tone="success">{t("purchased")}</Badge>
        ) : (
          <Badge tone={lead.remaining_slots > 1 ? "neutral" : "warning"}>
            {t("slotsLeft", { count: lead.remaining_slots })}
          </Badge>
        )}
      </div>

      {cover && (
        <div className="relative h-40 w-full overflow-hidden rounded-lg bg-slate-100">
          <Image
            src={cover}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, 33vw"
            className="object-cover"
          />
        </div>
      )}

      <div className="flex-1 space-y-1">
        <h3 className="font-semibold text-slate-900">{lead.title}</h3>
        <p className="line-clamp-3 text-sm text-slate-600">{lead.description}</p>
      </div>

      <dl className="space-y-1 text-sm text-slate-500">
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">{t("filterRadius")}</dt>
          <dd>
            {lead.city}
            {lead.distance_km !== null && (
              <> · {t("distanceFrom", { distance: formatDistance(lead.distance_km, locale) })}</>
            )}
          </dd>
        </div>
        <div>
          <dt className="sr-only">{tLead("publishedAgo", { when: "" })}</dt>
          <dd>{tLead("publishedAgo", { when: formatRelative(lead.created_at, locale) })}</dd>
        </div>
      </dl>

      <div className="flex items-center justify-between border-t border-slate-100 pt-3">
        <span className="font-semibold text-slate-900">
          {formatMoney(lead.price, locale)}
        </span>
        <Link
          href={`${path(locale, "projects")}/${lead.id}`}
          className="text-sm font-semibold text-brand-600 hover:text-brand-700"
        >
          {t("viewDetail")} →
        </Link>
      </div>
    </Card>
  );
}
