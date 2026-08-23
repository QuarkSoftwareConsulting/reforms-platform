import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AuthGate } from "@/components/features/AuthGate";
import { PurchaseHistory } from "@/components/features/PurchaseHistory";
import { Skeleton } from "@/components/ui/Card";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "purchases" });
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function MyContactsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  return (
    <AuthGate>
      {/* Lee ?purchase= y ?status= al volver de la pasarela de pago. */}
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <PurchaseHistory />
      </Suspense>
    </AuthGate>
  );
}
