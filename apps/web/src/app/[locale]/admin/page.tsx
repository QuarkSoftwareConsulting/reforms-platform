import { getTranslations, setRequestLocale } from "next-intl/server";

import { AdminGate } from "@/components/features/AdminGate";
import { AdminPanel } from "@/components/features/AdminPanel";
import { Container } from "@/components/ui/Container";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "admin" });
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function AdminPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);
  return (
    <Container className="py-10">
      <AdminGate>
        <AdminPanel />
      </AdminGate>
    </Container>
  );
}
