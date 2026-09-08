import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Badge, Card } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { isAppLocale, path, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { Category } from "@/types/api";

const MAX_PROFESSIONALS = 3;

/**
 * Landing renderizada en servidor.
 *
 * Es la pagina que tiene que indexar Google, asi que se renderiza entera en
 * servidor con el catalogo real de oficios y sin JavaScript de cliente.
 */
export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "home" });

  let categories: Category[] = [];
  try {
    categories = await leadsService.categories(locale);
  } catch {
    // Si el API no responde, la landing sigue siendo util: mostramos el resto.
  }

  const cheapest = categories.reduce<Category | null>(
    (min, category) =>
      min === null ||
      category.suggested_lead_price.amount_cents < min.suggested_lead_price.amount_cents
        ? category
        : min,
    null,
  );

  return (
    <div className="space-y-14">
      <section className="space-y-6 py-8 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          {t("title")}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-slate-600">{t("subtitle")}</p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href={path(locale, "publish")}
            className="inline-flex h-13 items-center rounded-lg bg-brand-600 px-7 font-semibold text-white hover:bg-brand-700"
          >
            {t("clientCta")}
          </Link>
          <Link
            href={path(locale, "register")}
            className="inline-flex h-13 items-center rounded-lg border border-brand-200 bg-white px-7 font-semibold text-brand-700 hover:bg-brand-50"
          >
            {t("proCta")}
          </Link>
        </div>
      </section>

      <section className="space-y-6">
        <h2 className="text-center text-2xl font-bold text-slate-900">{t("howItWorks")}</h2>
        <div className="grid gap-5 md:grid-cols-2">
          {(
            [
              { title: t("clientTitle"), ns: "clientSteps" as const, tone: "brand" as const },
              { title: t("proTitle"), ns: "proSteps" as const, tone: "warning" as const },
            ]
          ).map((block) => (
            <Card key={block.ns} className="space-y-4">
              <h3 className="text-lg font-semibold text-slate-900">{block.title}</h3>
              <ol className="space-y-3">
                {(["one", "two", "three"] as const).map((step, index) => (
                  <li key={step} className="flex gap-3 text-sm text-slate-700">
                    <Badge tone={block.tone} className="size-6 shrink-0 justify-center">
                      {index + 1}
                    </Badge>
                    <span>
                      {t(`${block.ns}.${step}`, { maxProfessionals: MAX_PROFESSIONALS })}
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          ))}
        </div>
      </section>

      {categories.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-slate-900">{t("trades")}</h2>
          <ul className="flex flex-wrap gap-2">
            {categories.map((category) => (
              <li key={category.id}>
                <Link
                  href={`${path(locale, "publish")}?category=${category.slug}`}
                  className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-brand-400 hover:text-brand-700"
                >
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
          {cheapest && (
            <p className="text-sm text-slate-500">
              {t("priceNote", { price: formatMoney(cheapest.suggested_lead_price, locale) })}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
