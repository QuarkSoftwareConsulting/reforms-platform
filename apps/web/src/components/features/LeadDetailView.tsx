"use client";

import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { ContactPanel } from "@/components/features/ContactPanel";
import { PurchaseButton } from "@/components/features/PurchaseButton";
import { Alert } from "@/components/ui/Alert";
import { Badge, Card, Skeleton } from "@/components/ui/Card";
import { formatRelative } from "@/helpers/date";
import { formatDistance } from "@/helpers/distance";
import { useApiError } from "@/hooks/useApiError";
import { path, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { LeadDetail } from "@/types/api";

/** Detalle de una solicitud: descripcion, fotos y bloque de compra o contacto. */
export function LeadDetailView({ leadId }: { leadId: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("lead");
  const tProjects = useTranslations("projects");
  const translateError = useApiError();

  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await leadsService.detail(leadId, locale));
    } catch (caught) {
      setError(translateError(caught));
    } finally {
      setLoading(false);
    }
  }, [leadId, locale, translateError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Alert tone="error">{error}</Alert>
        <Link href={path(locale, "projects")} className="text-brand-700 hover:underline">
          ← {t("backToProjects")}
        </Link>
      </div>
    );
  }

  const { lead } = detail;

  return (
    <div className="space-y-6">
      <Link
        href={path(locale, "projects")}
        className="inline-block text-sm text-brand-700 hover:underline"
      >
        ← {t("backToProjects")}
      </Link>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-5">
          <header className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">{lead.category.name}</Badge>
              <Badge tone={lead.remaining_slots > 1 ? "neutral" : "warning"}>
                {tProjects("slotsLeft", { count: lead.remaining_slots })}
              </Badge>
            </div>
            <h1 className="text-3xl font-bold text-slate-900">{lead.title}</h1>
            <p className="text-sm text-slate-500">
              {lead.city}, {lead.province}
              {lead.distance_km !== null && (
                <>
                  {" · "}
                  {tProjects("distanceFrom", {
                    distance: formatDistance(lead.distance_km, locale),
                  })}
                </>
              )}
              {" · "}
              {t("publishedAgo", { when: formatRelative(lead.created_at, locale) })}
            </p>
          </header>

          <Card>
            <p className="whitespace-pre-line text-slate-700">{lead.description}</p>
          </Card>

          {lead.photo_urls.length > 0 && (
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {lead.photo_urls.map((url) => (
                <li key={url} className="relative h-40 overflow-hidden rounded-lg bg-slate-100">
                  <Image
                    src={url}
                    alt=""
                    fill
                    sizes="(max-width: 640px) 50vw, 33vw"
                    className="object-cover"
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <aside className="space-y-4">
          {detail.contact ? (
            <ContactPanel contact={detail.contact} />
          ) : (
            <PurchaseButton detail={detail} />
          )}
        </aside>
      </div>
    </div>
  );
}
