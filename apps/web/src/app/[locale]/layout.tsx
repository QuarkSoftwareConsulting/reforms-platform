import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/features/SiteHeader";
import { AuthProvider } from "@/hooks/useAuth";
import { isAppLocale, locales, type AppLocale } from "@/i18n/routing";

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
  return {
    title: { default: `${t("title")} | Reforma Hub`, template: "%s | Reforma Hub" },
    description: t("subtitle"),
    // Una URL canonica por idioma, que es lo que necesita el SEO local.
    alternates: {
      canonical: `/${locale}`,
      languages: Object.fromEntries(locales.map((l) => [l, `/${l}`])),
    },
    openGraph: { title: t("title"), description: t("subtitle"), locale },
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
    <html lang={locale}>
      <body className="min-h-dvh">
        <NextIntlClientProvider messages={messages}>
          <AuthProvider locale={locale as AppLocale}>
            <SiteHeader />
            <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
