"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/Card";
import { useAuth } from "@/hooks/useAuth";
import { path, type AppLocale } from "@/i18n/routing";

/** Puerta UX del backoffice; el API conserva la autorizacion real. */
export function AdminGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const locale = useLocale() as AppLocale;
  const t = useTranslations("common");
  const needsLogin = auth.firebaseUser === null;
  const denied = !auth.loading && auth.isAuthenticated && auth.me?.role !== "admin";

  useEffect(() => {
    if (needsLogin) router.replace(path(locale, "login"));
    if (denied) router.replace(path(locale, "home"));
  }, [denied, locale, needsLogin, router]);

  if (auth.loading || needsLogin || denied) {
    return <Skeleton className="h-80 w-full" aria-label={t("loading")} />;
  }
  return <>{children}</>;
}
