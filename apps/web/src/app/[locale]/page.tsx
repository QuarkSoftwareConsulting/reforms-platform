import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { HomeJsonLd } from "@/components/features/HomeJsonLd";
import { Container } from "@/components/ui/Container";
import { LiveDot, Tag } from "@/components/ui/Card";
import { formatMoney } from "@/helpers/currency";
import { isAppLocale, path, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { Category } from "@/types/api";

/** Cap de plazas por solicitud. Lo impone el backend; aqui solo se comunica. */
const MAX_PROFESSIONALS = 3;

/** Oficios que caben en el tablero del hero sin alargar la primera pantalla. */
const BOARD_SIZE = 5;

/** Catalogo cacheado 5 minutos en el servicio: la home se sirve estatica con ISR. */
export const revalidate = 300;

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

  const publishHref = path(locale, "publish");
  const tradeHref = (category: Category) => `${publishHref}?category=${category.slug}`;

  return (
    <>
      <HomeJsonLd locale={locale} categories={categories} />

      {/* ---------------------------------------------------------------- Hero */}
      <section className="bg-surface">
        <Container className="grid gap-14 py-14 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-16">
          <div>
            <p className="mb-4 text-label font-semibold uppercase text-brand">
              {t("heroEyebrow")}
            </p>
            <h1 className="text-[2.5rem] font-extrabold leading-[1.05] tracking-[-1.4px] text-ink sm:text-[3.25rem] lg:text-[3.875rem]">
              {t.rich("heroTitle", {
                mark: (chunks) => <span className="vr-highlight">{chunks}</span>,
              })}
            </h1>
            <p className="mt-5 max-w-[480px] text-[19px] leading-[1.6] text-secondary">
              {t("heroSubtitle")}
            </p>

            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href={path(locale, "register")}
                className="inline-flex min-h-[56px] items-center rounded-control bg-brand px-8 text-[17px] font-semibold text-surface transition-colors hover:bg-brand-hover"
              >
                {t("heroProCta")}
              </Link>
              <Link
                href={publishHref}
                className="inline-flex min-h-[56px] items-center rounded-control border-[1.5px] border-line-strong px-8 text-[17px] font-semibold text-ink transition-colors hover:border-brand hover:text-brand"
              >
                {t("heroClientCta")}
              </Link>
            </div>

            {categories.length > 0 && (
              <ul className="mt-7 flex flex-wrap gap-2">
                {categories.slice(0, 6).map((category) => (
                  <li key={category.id}>
                    <Link
                      href={tradeHref(category)}
                      className="inline-flex rounded-full border border-line px-3.5 py-2 text-sm text-ink transition-colors hover:border-brand hover:text-brand"
                    >
                      {category.name}
                    </Link>
                  </li>
                ))}
                <li>
                  <Link
                    href="#oficios"
                    className="inline-flex rounded-full border border-line px-3.5 py-2 text-sm text-brand"
                  >
                    {t("heroMoreTrades")}
                  </Link>
                </li>
              </ul>
            )}
          </div>

          {/* Tablero: oficios reales del catalogo con su precio real. No hay
              fichas de ejemplo — el listado de contactos exige sesion. */}
          {categories.length > 0 && (
            <aside className="rounded-panel border border-line bg-page p-5">
              <div className="mb-3.5 flex items-center justify-between gap-3 px-1">
                <p className="text-sm font-semibold text-ink">{t("board.title")}</p>
                <LiveDot>{t("board.live")}</LiveDot>
              </div>
              <ul className="space-y-2.5">
                {categories.slice(0, BOARD_SIZE).map((category) => (
                  <li key={category.id}>
                    <Link
                      href={tradeHref(category)}
                      className="flex items-center justify-between gap-4 rounded-option border border-line bg-surface px-[18px] py-4 transition-colors hover:border-brand"
                    >
                      <span className="min-w-0">
                        <Tag>{category.name}</Tag>
                      </span>
                      <span className="shrink-0 text-right">
                        <span className="block text-[11px] uppercase tracking-[0.7px] text-muted">
                          {t("board.price")}
                        </span>
                        <span className="block text-[19px] font-bold text-brand">
                          {formatMoney(category.suggested_lead_price, locale)}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              <Link
                href="#oficios"
                className="mt-3.5 inline-block px-1 text-sm font-semibold text-brand underline underline-offset-4 hover:text-brand-hover"
              >
                {t("board.all", { count: categories.length })}
              </Link>
            </aside>
          )}
        </Container>
      </section>

      {/* ------------------------------------------------- Como se valida */}
      <section id="como-validamos" className="scroll-mt-20 border-t border-line bg-page py-16">
        <Container>
          <SectionHeading title={t("validation.title")} subtitle={t("validation.subtitle")} />
          <ol className="mt-10 grid gap-5 md:grid-cols-3">
            {(["one", "two", "three"] as const).map((step, index) => (
              <li
                key={step}
                className="rounded-card border border-line bg-surface p-6"
              >
                <span className="text-[13px] font-bold tracking-[1.2px] text-brand">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-2 text-card-title font-semibold text-ink">
                  {t(`validation.${step}.title`)}
                </h3>
                <p className="mt-2 text-[14.5px] leading-[1.6] text-secondary">
                  {t(`validation.${step}.body`)}
                </p>
              </li>
            ))}
          </ol>
        </Container>
      </section>

      {/* ------------------------------------------------------- Oficios */}
      {categories.length > 0 && (
        <section id="oficios" className="scroll-mt-20 bg-surface py-16">
          <Container>
            <SectionHeading title={t("trades.title")} subtitle={t("trades.subtitle")} />
            <ul className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {categories.map((category) => (
                <li key={category.id}>
                  <Link
                    href={tradeHref(category)}
                    className="flex h-full items-center justify-between gap-4 rounded-option border border-line bg-surface px-[18px] py-4 transition-colors hover:border-brand"
                  >
                    <span className="text-[15px] font-semibold text-ink">{category.name}</span>
                    <span className="shrink-0 text-[17px] font-bold text-brand">
                      {formatMoney(category.suggested_lead_price, locale)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-5 text-[14.5px] text-muted">{t("trades.note")}</p>
          </Container>
        </section>
      )}

      {/* ------------------------------------------------- Por que distinto */}
      <section className="border-t border-line bg-page py-16">
        <Container>
          <SectionHeading title={t("why.title")} subtitle={t("why.subtitle")} />
          <ul className="mt-10 grid gap-5 sm:grid-cols-2">
            {(["cap", "price", "noFee", "privacy"] as const).map((item) => (
              <li key={item} className="rounded-card border border-line bg-surface p-6">
                <h3 className="text-card-title font-semibold text-ink">
                  {t(`why.${item}.title`, { maxProfessionals: MAX_PROFESSIONALS })}
                </h3>
                <p className="mt-2 text-[14.5px] leading-[1.6] text-secondary">
                  {t(`why.${item}.body`, { maxProfessionals: MAX_PROFESSIONALS })}
                </p>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      {/* --------------------------------------------------------- Precio */}
      <section id="precios" className="scroll-mt-20 bg-surface py-16">
        <Container>
          <div className="rounded-panel border border-line bg-page p-8 sm:p-10">
            <p className="text-label font-semibold uppercase text-brand">
              {t("pricing.eyebrow")}
            </p>
            <h2 className="mt-3 max-w-2xl text-h2 font-bold text-ink">
              {cheapest
                ? t("pricing.headline", {
                    price: formatMoney(cheapest.suggested_lead_price, locale),
                  })
                : t("pricing.headlineFallback")}
            </h2>
            <p className="mt-4 max-w-2xl text-[15.5px] leading-[1.6] text-secondary">
              {t("pricing.body")}
            </p>
            <Link
              href={path(locale, "register")}
              className="mt-7 inline-flex min-h-12 items-center rounded-control border-[1.5px] border-line-strong bg-surface px-[26px] text-base font-semibold text-ink transition-colors hover:border-brand hover:text-brand"
            >
              {t("pricing.cta")}
            </Link>
          </div>
        </Container>
      </section>

      {/* ---------------------------------------------------- CTA cliente */}
      <section className="bg-ink py-14">
        <Container className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-h2 font-bold text-surface">{t("clientBanner.title")}</h2>
            <p className="mt-2 max-w-xl text-[15.5px] leading-[1.6] text-line-strong">
              {t("clientBanner.body")}
            </p>
          </div>
          <Link
            href={publishHref}
            className="inline-flex min-h-[56px] shrink-0 items-center justify-center rounded-control bg-accent px-8 text-[17px] font-semibold text-ink transition-colors hover:bg-accent-hover"
          >
            {t("clientBanner.cta")}
          </Link>
        </Container>
      </section>
    </>
  );
}

function SectionHeading({ title, subtitle }: { title: string; subtitle: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <h2 className="text-h2 font-bold text-ink">{title}</h2>
      <p className="mt-3 text-[15.5px] leading-[1.6] text-secondary">{subtitle}</p>
    </div>
  );
}
