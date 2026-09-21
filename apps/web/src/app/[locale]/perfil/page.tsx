import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuthGate } from "@/components/features/AuthGate";
import { ProfileForm } from "@/components/features/ProfileForm";
import { Alert } from "@/components/ui/Alert";
import { Container } from "@/components/ui/Container";
import { isAppLocale, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { Category } from "@/types/api";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "profile" });
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function ProfilePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  const tErrors = await getTranslations({ locale, namespace: "errors" });

  let categories: Category[] = [];
  let loadError = false;
  try {
    categories = await leadsService.categories(locale);
  } catch {
    loadError = true;
  }

  return (
    <Container size="form" className="py-10">
      {/* `requireProfile: false` — esta es justamente la pagina donde se crea. */}
      <AuthGate requireProfile={false}>
        {loadError ? (
          <Alert tone="error">{tErrors("network")}</Alert>
        ) : (
          <ProfileForm categories={categories} />
        )}
      </AuthGate>
    </Container>
  );
}
