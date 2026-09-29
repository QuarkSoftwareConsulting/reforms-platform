import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AuthGate } from "@/components/features/AuthGate";
import { SubscriptionPanel } from "@/components/features/SubscriptionPanel";
import { Skeleton } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "subscription" });
  return { title: t("title"), robots: { index: false, follow: false } };
}

export default async function SubscriptionPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: raw } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  return (
    <Container size="form" className="py-10">
      <AuthGate>
        {/* Lee ?status= al volver del checkout de la recarga. */}
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <SubscriptionPanel />
        </Suspense>
      </AuthGate>
    </Container>
  );
}
