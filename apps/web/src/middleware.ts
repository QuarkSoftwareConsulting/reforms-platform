import createMiddleware from "next-intl/middleware";

import { defaultLocale, locales } from "@/i18n/routing";

/**
 * Redirige "/" al idioma detectado en el navegador y valida el segmento `[lang]`.
 * `localePrefix: "always"` mantiene una URL canonica por idioma, que es lo que
 * necesita el SEO local ("carpinteros en Madrid" / "carpenters in Miami").
 */
export default createMiddleware({
  locales,
  defaultLocale,
  localePrefix: "always",
  localeDetection: true,
});

export const config = {
  matcher: ["/", "/(es|en)/:path*", "/((?!api|_next|_vercel|.*\\..*).*)"],
};
