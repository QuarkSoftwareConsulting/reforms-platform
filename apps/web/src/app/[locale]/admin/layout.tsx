import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { AdminGate } from "@/components/features/AdminGate";
import { AdminNav } from "@/components/features/AdminNav";
import { Container } from "@/components/ui/Container";
import { AdminPendingProvider } from "@/hooks/useAdminPending";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "admin" });
  // Las secciones heredan `robots`: solo cambian el titulo.
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function AdminLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "admin" });
  return (
    <Container className="py-10">
      <AdminGate>
        <AdminPendingProvider>
          <div className="space-y-8">
            <header className="space-y-6">
              <div className="space-y-1">
                <h1 className="text-h1 font-bold text-ink">{t("title")}</h1>
                <p className="text-secondary">{t("subtitle")}</p>
              </div>
              <AdminNav />
            </header>
            {children}
          </div>
        </AdminPendingProvider>
      </AdminGate>
    </Container>
  );
}
