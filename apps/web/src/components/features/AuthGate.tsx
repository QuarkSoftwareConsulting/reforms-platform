"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/Card";
import { useAuth } from "@/hooks/useAuth";
import { path, type AppLocale } from "@/i18n/routing";

/**
 * Puerta de acceso en cliente para las rutas de profesional.
 *
 * Es una comodidad de UX, no una medida de seguridad: la autorizacion real la
 * aplica el backend en cada peticion. Sin sesion redirige al login; con sesion
 * pero sin perfil, al onboarding de perfil.
 */
export function AuthGate({
  children,
  requireProfile = true,
}: {
  children: ReactNode;
  requireProfile?: boolean;
}) {
  const auth = useAuth();
  const router = useRouter();
  const locale = useLocale() as AppLocale;
  const t = useTranslations("common");

  const needsLogin = auth.firebaseUser === null;
  const needsProfile = requireProfile && auth.isAuthenticated && !auth.loading && !auth.hasProfile;

  useEffect(() => {
    if (needsLogin) {
      router.replace(path(locale, "login"));
    } else if (needsProfile) {
      router.replace(path(locale, "profile"));
    }
  }, [needsLogin, needsProfile, router, locale]);

  if (auth.loading || needsLogin || needsProfile) {
    return (
      <div className="space-y-4" aria-label={t("loading")} aria-busy>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return <>{children}</>;
}
