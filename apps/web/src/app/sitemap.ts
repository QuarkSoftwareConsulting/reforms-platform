import type { MetadataRoute } from "next";

import { absoluteUrl } from "@/helpers/site";
import { locales, path } from "@/i18n/routing";
import type { routes } from "@/i18n/routing";

/** Solo rutas publicas: las zonas privadas ya se excluyen con `robots` en su metadata. */
const PUBLIC_ROUTES: (keyof typeof routes)[] = ["home", "publish", "login", "register"];

export default function sitemap(): MetadataRoute.Sitemap {
  return locales.flatMap((locale) =>
    PUBLIC_ROUTES.map((route) => ({
      url: absoluteUrl(path(locale, route) || `/${locale}`),
      lastModified: new Date(),
      changeFrequency: route === "home" ? ("daily" as const) : ("monthly" as const),
      priority: route === "home" ? 1 : 0.7,
      alternates: {
        languages: Object.fromEntries(
          locales.map((l) => [l, absoluteUrl(path(l, route) || `/${l}`)]),
        ),
      },
    })),
  );
}
