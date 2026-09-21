import { getTranslations } from "next-intl/server";

import { absoluteUrl, LOGO_PATH, siteUrl } from "@/helpers/site";
import { path, type AppLocale } from "@/i18n/routing";
import type { Category } from "@/types/api";

/**
 * Datos estructurados de la landing.
 *
 * Todo lo que se declara aqui sale del catalogo real del API: los oficios y sus
 * precios sugeridos. No se publica ninguna cifra que no pueda comprobarse.
 */
export async function HomeJsonLd({
  locale,
  categories,
}: {
  locale: AppLocale;
  categories: Category[];
}) {
  const t = await getTranslations({ locale, namespace: "home" });
  const tCommon = await getTranslations({ locale, namespace: "common" });

  const appName = tCommon("appName");
  const home = absoluteUrl(path(locale, "home") || "/");

  const graph: Record<string, unknown>[] = [
    {
      "@type": "Organization",
      "@id": `${siteUrl()}#organization`,
      name: appName,
      url: home,
      logo: absoluteUrl(LOGO_PATH),
      areaServed: { "@type": "Country", name: "ES" },
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl()}#website`,
      name: appName,
      url: home,
      inLanguage: locale,
      publisher: { "@id": `${siteUrl()}#organization` },
    },
  ];

  if (categories.length > 0) {
    graph.push({
      "@type": "ItemList",
      name: t("trades.title"),
      numberOfItems: categories.length,
      itemListElement: categories.map((category, index) => ({
        "@type": "ListItem",
        position: index + 1,
        item: {
          "@type": "Service",
          name: category.name,
          serviceType: category.name,
          provider: { "@id": `${siteUrl()}#organization` },
          areaServed: { "@type": "Country", name: "ES" },
          url: absoluteUrl(`${path(locale, "publish")}?category=${category.slug}`),
          offers: {
            "@type": "Offer",
            // El precio anunciado es el del contacto, no el de la reforma.
            price: (category.suggested_lead_price.amount_cents / 100).toFixed(2),
            priceCurrency: category.suggested_lead_price.currency,
            category: t("board.price"),
          },
        },
      })),
    });
  }

  return (
    <script
      type="application/ld+json"
      // El contenido es JSON generado aqui, no entrada de usuario.
      dangerouslySetInnerHTML={{
        __html: JSON.stringify({ "@context": "https://schema.org", "@graph": graph }),
      }}
    />
  );
}
