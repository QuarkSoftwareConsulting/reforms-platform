import Image from "next/image";
import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { HomeJsonLd } from "@/components/features/HomeJsonLd";
import { LandingIcon, type LandingIconName } from "@/components/ui/LandingIcon";
import { cn } from "@/helpers/cn";
import { formatMoney } from "@/helpers/currency";
import { isAppLocale, path, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { CatalogCategory, Money } from "@/types/api";

/** Cap de plazas por solicitud. Lo impone el backend; aqui solo se comunica. */
const MAX_PROFESSIONALS = 5;

/** Recarga mensual. La cobra el precio de Stripe (`SUBSCRIPTION_TOPUP_CENTS` en el API). */
const TOPUP_CENTS = 1800;

/**
 * Oficios destacados de la landing.
 *
 * No son categorias: son servicios del catalogo (`services.csv`) con nombre corto
 * y foto. El precio es el sugerido de su categoria, que es lo que se cobra. Si el
 * API no devuelve la categoria o el servicio (retirado), la tarjeta no se pinta:
 * no anunciamos un oficio que no se puede publicar.
 */
const FEATURED_TRADES = [
  { key: "fullRenovation", image: "01_reforma_integral", category: "reformas", service: "reforma-integral" },
  { key: "bathrooms", image: "02_banos", category: "reformas", service: "reformas-banos" },
  { key: "kitchens", image: "03_cocinas", category: "reformas", service: "reformas-cocinas" },
  { key: "painting", image: "04_pintura", category: "obras-menores", service: "pintores" },
  { key: "electrical", image: "05_electricidad", category: "instaladores", service: "electricistas" },
  { key: "plumbing", image: "06_fontaneria", category: "obras-menores", service: "fontaneros" },
  { key: "carpentry", image: "07_carpinteria", category: "obras-menores", service: "carpinteros" },
  { key: "locksmith", image: "08_cerrajeria", category: "obras-menores", service: "cerrajeros" },
  { key: "airConditioning", image: "09_climatizacion", category: "instaladores", service: "aire-acondicionado" },
  { key: "glazing", image: "10_cristaleria", category: "obras-menores", service: "cristaleros" },
  { key: "gardening", image: "11_jardineria", category: "mantenimiento", service: "jardineros" },
  { key: "cleaning", image: "12_limpieza", category: "mantenimiento", service: "limpieza" },
] as const;

const STEPS: { key: "one" | "two" | "three"; icon: LandingIconName }[] = [
  { key: "one", icon: "review" },
  { key: "two", icon: "details" },
  { key: "three", icon: "decide" },
];

const ADVANTAGES: { key: "cap" | "price" | "topup" | "privacy"; icon: LandingIconName }[] = [
  { key: "cap", icon: "cap" },
  { key: "price", icon: "price" },
  { key: "topup", icon: "topup" },
  { key: "privacy", icon: "privacy" },
];

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

  let categories: CatalogCategory[] = [];
  try {
    categories = await leadsService.categories(locale);
  } catch {
    // Si el API no responde, la landing sigue siendo util: mostramos el resto.
  }

  const cheapest = categories.reduce<CatalogCategory | null>(
    (min, category) =>
      min === null ||
      category.suggested_lead_price.amount_cents < min.suggested_lead_price.amount_cents
        ? category
        : min,
    null,
  );

  const publishHref = path(locale, "publish");
  const projectsHref = path(locale, "projects");

  const trades = FEATURED_TRADES.flatMap((trade) => {
    const category = categories.find((c) => c.slug === trade.category);
    if (!category?.services.some((s) => s.slug === trade.service)) return [];
    return [
      {
        ...trade,
        price: category.suggested_lead_price,
        href: `${publishHref}?category=${trade.category}&service=${trade.service}`,
      },
    ];
  });

  return (
    <>
      <HomeJsonLd locale={locale} categories={categories} />

      {/* ---------------------------------------------------------------- Hero */}
      <section className="relative overflow-hidden bg-surface">
        <BleedPhoto src="/images/hero.png" alt={t("heroImageAlt")} priority />
        <div className={cn(WIDE, "relative py-10 lg:flex lg:min-h-[345px] lg:items-center lg:py-12 lg:pl-[72px]")}>
          <div className="lg:max-w-[50%]">
            <h1 className="text-[2.25rem] font-bold leading-[1.15] tracking-[-0.8px] text-navy lg:text-[2.625rem]">
              {t("heroTitle")}
            </h1>
            <p className="mt-3 max-w-[600px] text-[17px] leading-[1.5] text-secondary">
              {t("heroSubtitle")}
            </p>

            <div className="mt-6 flex flex-wrap gap-4">
              <Link
                href={projectsHref}
                className="inline-flex min-h-[50px] items-center rounded-tag bg-brand px-8 text-[16px] font-semibold text-surface transition-colors hover:bg-brand-hover"
              >
                {t("heroProCta")}
              </Link>
              <Link
                href={publishHref}
                className="inline-flex min-h-[50px] items-center rounded-tag border border-line-strong bg-surface px-8 text-[16px] font-semibold text-navy transition-colors hover:border-brand hover:text-brand"
              >
                {t("heroClientCta")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- Oficios */}
      {trades.length > 0 && (
        <section id="oficios" className="scroll-mt-20 bg-surface pb-5 pt-7">
          <div className={WIDE}>
            <SectionHeading
              eyebrow={t("trades.eyebrow")}
              title={t("trades.title")}
              subtitle={t("trades.subtitle")}
            />
            <ul className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {trades.map((trade) => (
                <li key={trade.key}>
                  <Link
                    href={trade.href}
                    className={cn(SOFT_CARD, "group block h-full overflow-hidden")}
                  >
                    <span className="relative block aspect-[8/5] bg-page">
                      <Image
                        src={`/images/${trade.image}.webp`}
                        alt=""
                        fill
                        sizes="(min-width: 1024px) 200px, (min-width: 640px) 33vw, 50vw"
                        className="object-cover"
                      />
                    </span>
                    <span className="block px-3.5 pb-3.5 pt-2.5">
                      <span className="block text-[15px] font-bold text-navy group-hover:text-brand">
                        {t(`trades.items.${trade.key}`)}
                      </span>
                      <span className="mt-1 block text-[15px] text-ink">
                        {t("trades.from", { price: formatPrice(trade.price, locale) })}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <div className="mt-4 text-center">
              <Link
                href={publishHref}
                className="inline-flex items-center gap-1.5 text-[15px] font-semibold text-brand hover:text-brand-hover"
              >
                {t("trades.all")}
                <span aria-hidden>→</span>
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* ------------------------------------------------- Como se valida */}
      <section id="como-validamos" className="scroll-mt-20 bg-sky py-6">
        <div className={WIDE}>
          <SectionHeading
            eyebrow={t("validation.eyebrow")}
            title={t("validation.title")}
            subtitle={t("validation.subtitle")}
          />
          <ol className="mt-6 grid gap-4 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.key} className={cn(SOFT_CARD, "flex gap-4 p-5 lg:px-6")}>
                <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[16px] font-bold text-accent-strong">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <LandingIcon name={step.icon} className="size-14" />
                  <h3 className="mt-3 text-[18px] font-bold leading-[1.3] text-navy">
                    {t(`validation.${step.key}.title`)}
                  </h3>
                  <p className="mt-1 text-[15.5px] leading-[1.45] text-secondary">
                    {t(`validation.${step.key}.body`)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ------------------------------------------------------- Ventajas */}
      <section className="bg-sky-soft py-6">
        <div className={WIDE}>
          <SectionHeading
            eyebrow={t("why.eyebrow")}
            title={t("why.title")}
            subtitle={t("why.subtitle")}
          />
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {ADVANTAGES.map((item) => (
              <li key={item.key} className={cn(SOFT_CARD, "px-5 py-4 lg:px-7")}>
                <LandingIcon name={item.icon} className="size-16" />
                <h3 className="mt-3 text-[18px] font-bold leading-[1.3] text-navy">
                  {t(`why.${item.key}.title`)}
                </h3>
                <p className="mt-1.5 text-[15.5px] leading-[1.45] text-secondary">
                  {t(`why.${item.key}.body`, {
                    maxProfessionals: MAX_PROFESSIONALS,
                    amount: formatPrice(
                      { amount_cents: TOPUP_CENTS, currency: "EUR", formatted: "" },
                      locale,
                    ),
                  })}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* --------------------------------------------------------- Precio */}
      <section id="precios" className="scroll-mt-20 bg-surface py-6">
        <div className={WIDE}>
          <SectionHeading
            eyebrow={t("pricing.eyebrow")}
            title={
              cheapest
                ? t("pricing.headline", {
                    price: formatPrice(cheapest.suggested_lead_price, locale),
                  })
                : t("pricing.headlineFallback")
            }
            subtitle={t("pricing.body")}
          />
          <div className="mt-5 text-center">
            <Link
              href={projectsHref}
              className="inline-flex min-h-[44px] items-center rounded-tag bg-brand px-7 text-[16px] font-semibold text-surface transition-colors hover:bg-brand-hover"
            >
              {t("pricing.cta")}
            </Link>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- Particulares */}
      <section className="relative overflow-hidden bg-surface">
        <BleedPhoto src="/images/bottom.png" alt={t("clientBanner.imageAlt")} />
        <div className={cn(WIDE, "relative py-8 lg:flex lg:min-h-[232px] lg:items-center")}>
          <div className="lg:max-w-[44%]">
            <p className="text-[12px] font-semibold uppercase tracking-[0.6px] text-brand">
              {t("clientBanner.eyebrow")}
            </p>
            <h2 className="mt-1.5 text-[32px] font-bold leading-[1.2] tracking-[-0.5px] text-navy">
              {t("clientBanner.title")}
            </h2>
            <p className="mt-2 text-[16px] leading-[1.45] text-secondary">
              {t("clientBanner.body")}
            </p>
            <Link
              href={publishHref}
              className="mt-4 inline-flex min-h-[42px] items-center rounded-tag bg-cta px-7 text-[17px] font-bold text-surface transition-colors hover:bg-cta-hover"
            >
              {t("clientBanner.cta")}
            </Link>
            <p className="mt-3 text-[15px] text-secondary">{t("clientBanner.note")}</p>
          </div>
        </div>
      </section>
    </>
  );
}

/** Ancho de las secciones de la landing: mas ancho que el de la app, como en el diseno. */
const WIDE = "mx-auto w-full max-w-[1366px] px-5 sm:px-12";

/** Tarjeta de la landing: sin borde y con sombra suave, como en el diseno. */
const SOFT_CARD = "rounded-tag bg-surface shadow-[0_2px_10px_rgba(21,40,74,0.08)]";

/** Precio sin decimales cuando es redondo: "Desde 5 €" se lee mejor que "5,00 €". */
function formatPrice(money: Money, locale: AppLocale): string {
  return formatMoney(money, locale, { trimZeroCents: true });
}

/**
 * Foto a sangre en la mitad derecha de la seccion, fundida con el fondo por la
 * izquierda para que el texto no quede recortado contra el borde de la imagen.
 * En movil va debajo del texto, sin fundido.
 */
function BleedPhoto({ src, alt, priority }: { src: string; alt: string; priority?: boolean }) {
  return (
    <div className="relative aspect-[16/10] lg:absolute lg:inset-y-0 lg:right-0 lg:aspect-auto lg:w-[56%]">
      <Image
        src={src}
        alt={alt}
        fill
        priority={priority}
        sizes="(min-width: 1024px) 56vw, 100vw"
        className="object-cover object-[center_30%]"
      />
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 -ml-px hidden w-2/5 bg-gradient-to-r from-surface from-10% via-surface/60 to-transparent lg:block"
      />
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-5xl text-center">
      <p className="text-[12px] font-semibold uppercase tracking-[0.6px] text-brand">{eyebrow}</p>
      <h2 className="mt-1 text-[28px] font-bold leading-[1.25] tracking-[-0.5px] text-navy">
        {title}
      </h2>
      <p className="mt-1.5 text-[16px] leading-[1.5] text-secondary">{subtitle}</p>
    </div>
  );
}
