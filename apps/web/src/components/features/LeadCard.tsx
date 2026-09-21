import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";

import { Seal, Tag } from "@/components/ui/Card";
import { cn } from "@/helpers/cn";
import { formatMoney } from "@/helpers/currency";
import { formatRelative } from "@/helpers/date";
import { formatDistance } from "@/helpers/distance";
import { path } from "@/i18n/routing";
import type { AppLocale } from "@/i18n/routing";
import type { LeadPublic } from "@/types/api";

/**
 * Tarjeta de contacto del explorador.
 *
 * Recibe un `LeadPublic`, cuyo tipo no incluye datos de contacto: es
 * estructuralmente imposible que esta tarjeta filtre la PII del cliente.
 *
 * El orden de los bloques lo fija el sistema de diseno y no es decorativo: el
 * precio del contacto tiene que verse siempre antes de llegar al boton.
 */
export function LeadCard({ lead }: { lead: LeadPublic }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("projects");
  const tLead = useTranslations("lead");
  const cover = lead.photo_urls[0];
  const closed = lead.remaining_slots === 0 && !lead.already_purchased;
  const href = `${path(locale, "projects")}/${lead.id}`;

  return (
    <article
      className={cn(
        "flex h-full flex-col gap-3.5 rounded-card border border-line bg-surface p-6",
        closed && "opacity-55",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <Tag tone={closed ? "neutral" : "trade"}>{lead.category.name}</Tag>
        {lead.already_purchased ? (
          <Tag tone="accent">{t("purchased")}</Tag>
        ) : (
          <Seal>{t("slotsLeft", { count: lead.remaining_slots })}</Seal>
        )}
      </div>

      {cover && !closed && (
        <div className="relative h-40 w-full overflow-hidden rounded-option bg-page">
          <Image
            src={cover}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, 33vw"
            className="object-cover"
          />
        </div>
      )}

      <div className="flex-1 space-y-2">
        <h3 className="text-card-title font-semibold text-ink">{lead.title}</h3>
        {!closed && (
          <p className="line-clamp-3 text-[14.5px] leading-[1.6] text-secondary">
            {lead.description}
          </p>
        )}
        <p className="text-help text-muted">
          {lead.city}
          {lead.distance_km !== null && (
            <> · {t("distanceFrom", { distance: formatDistance(lead.distance_km, locale) })}</>
          )}
          {" · "}
          {tLead("publishedAgo", { when: formatRelative(lead.created_at, locale) })}
        </p>
      </div>

      <div className="flex items-end justify-between gap-3 border-t border-divider pt-3.5">
        <span>
          <span className="block text-[11px] uppercase tracking-[0.7px] text-muted">
            {t("contactPrice")}
          </span>
          <span className="block text-card-title font-bold text-brand">
            {formatMoney(lead.price, locale)}
          </span>
        </span>
      </div>

      {!closed && (
        <Link
          href={href}
          className={cn(
            "inline-flex min-h-12 w-full items-center justify-center rounded-control",
            "px-[26px] text-base font-semibold transition-colors",
            lead.already_purchased
              ? "bg-brand text-surface hover:bg-brand-hover"
              : "bg-accent text-ink hover:bg-accent-hover",
          )}
        >
          {t("viewDetail")}
        </Link>
      )}
    </article>
  );
}
