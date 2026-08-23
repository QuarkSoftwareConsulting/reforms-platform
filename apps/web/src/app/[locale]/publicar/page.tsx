import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { LeadWizard } from "@/components/features/LeadWizard";
import { Alert } from "@/components/ui/Alert";
import { Skeleton } from "@/components/ui/Card";
import { isAppLocale, type AppLocale } from "@/i18n/routing";
import { leadsService } from "@/services/leads.service";
import type { Category } from "@/types/api";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "publish" });
  return { title: t("title") };
}

/**
 * Publicacion de solicitud: publica, sin login.
 *
 * El catalogo de oficios se carga en servidor para que el primer paso del
 * formulario se pinte lleno, sin un salto de carga en cliente.
 */
export default async function PublishPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "publish" });
  const tErrors = await getTranslations({ locale, namespace: "errors" });

  let categories: Category[] = [];
  let loadError = false;
  try {
    categories = await leadsService.categories(locale);
  } catch {
    loadError = true;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold text-slate-900">{t("title")}</h1>
      {loadError ? (
        <Alert tone="error">{tErrors("network")}</Alert>
      ) : (
        // El wizard lee ?category= de la URL, asi que se suspende en el prerender.
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <LeadWizard categories={categories} />
        </Suspense>
      )}
    </div>
  );
}
