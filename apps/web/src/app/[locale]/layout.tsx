import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/features/SiteFooter";
import { SiteHeader } from "@/components/features/SiteHeader";
import { LOGO_PATH, LOGO_SIZE, siteUrl } from "@/helpers/site";
import { AuthProvider } from "@/hooks/useAuth";
import { isAppLocale, locales, type AppLocale } from "@/i18n/routing";

/**
 * Poppins autohospedada por `next/font`.
 *
 * Servirla desde Google bloquearia el primer render con una peticion a otro
 * dominio; asi el archivo sale del mismo origen, con `swap` y sin salto de
 * maquetacion.
 */
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-sans",
});

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  if (!isAppLocale(locale)) return {};

  const t = await getTranslations({ locale, namespace: "home" });
  const tCommon = await getTranslations({ locale, namespace: "common" });
  const appName = tCommon("appName");

  return {
    metadataBase: new URL(siteUrl()),
    title: { default: `${t("title")} | ${appName}`, template: `%s | ${appName}` },
    description: t("subtitle"),
    applicationName: appName,
    // Una URL canonica por idioma, que es lo que necesita el SEO local.
    alternates: {
      canonical: `/${locale}`,
      languages: Object.fromEntries(locales.map((l) => [l, `/${l}`])),
    },
    openGraph: {
      type: "website",
      siteName: appName,
      title: t("title"),
      description: t("subtitle"),
      locale,
      url: `/${locale}`,
      images: [{ url: LOGO_PATH, ...LOGO_SIZE, alt: appName }],
    },
    twitter: {
      card: "summary_large_image",
      title: t("title"),
      description: t("subtitle"),
      images: [LOGO_PATH],
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    notFound();
  }
  // Habilita el renderizado estatico de las paginas de este segmento.
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} className={poppins.variable}>
      <body className="flex min-h-dvh flex-col">
        <NextIntlClientProvider messages={messages}>
          <AuthProvider locale={locale as AppLocale}>
            <SiteHeader />
            {/* Cada pagina fija su propio ancho: el home necesita secciones a
                sangre completa que un contenedor aqui impediria. */}
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
