import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuthGate } from "@/components/features/AuthGate";
import { ProjectExplorer } from "@/components/features/ProjectExplorer";
import { Container } from "@/components/ui/Container";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "projects" });
  // Zona privada: no interesa que la indexen.
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function ProjectsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  return (
    <Container className="py-10">
      <AuthGate>
        <ProjectExplorer />
      </AuthGate>
    </Container>
  );
}
