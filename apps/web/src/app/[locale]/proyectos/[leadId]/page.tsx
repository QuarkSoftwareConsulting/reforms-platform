import { setRequestLocale } from "next-intl/server";

import { AuthGate } from "@/components/features/AuthGate";
import { LeadDetailView } from "@/components/features/LeadDetailView";
import { Container } from "@/components/ui/Container";
import { isAppLocale, type AppLocale } from "@/i18n/routing";

export const metadata = { robots: { index: false, follow: false } };

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ locale: string; leadId: string }>;
}) {
  const { locale: raw, leadId } = await params;
  const locale = (isAppLocale(raw) ? raw : "es") as AppLocale;
  setRequestLocale(locale);

  return (
    <Container className="py-10">
      <AuthGate>
        <LeadDetailView leadId={leadId} />
      </AuthGate>
    </Container>
  );
}
